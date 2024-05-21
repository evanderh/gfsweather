#!/usr/bin/env python

import os
import re
import logging
import shutil
import json
import tempfile
import subprocess
import argparse
from datetime import datetime
from logging.handlers import RotatingFileHandler

from osgeo import gdal
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import psycopg2

DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/postgres'
QUEUE_NAME = 'gfsweather'
RASTER_TABLE = 'public.rasters'

s3 = boto3.client('s3')
sqs = boto3.client('sqs')

SCALAR_BANDS = [
    # (grib element, grib short name)
    ('TMP', '2-HTGL')
]
def band_filter(band):
    metadata = band['metadata']['']
    for (element, short_name) in SCALAR_BANDS:
        if (element == metadata['GRIB_ELEMENT'] and
            short_name == metadata['GRIB_SHORT_NAME']):
            return True
    return False


class GFSSource():
    def __init__(self, bucket, key, metadata):
        self.bucket = bucket
        self.key = key
        self.metadata = metadata
        self.cycle_hour_key = '%s+%s' % (
            metadata['cycle_datetime'],
            metadata['forecast_hour']
        )
    
    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filename = os.path.join(self.tmpdir, 'gfs.grib')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tmpdir)

    def etl(self):
        logging.info('Starting ETL: %s' % self.key)
        self.extract()
        raster_sql = self.transform()
        self.load(raster_sql)
        logging.info('ETL complete: %s' % self.key)

    def extract(self):
        try:
            logging.info('Starting download')
            s3.download_file(self.bucket, self.key, self.filename)
            logging.info('Download successful')
        except ClientError as e:
            logging.error("Unable to download: %s" % e)
            raise

    def transform(self):
        bands = self._get_raster_info()
        self._translate_raster(bands)
        self._reproject_raster()
        return self._generate_raster_sql()

    def load(self, raster_sql):
        logging.info('Loading raster into db')
        try:
            conn = psycopg2.connect(DATABASE_URL)
            with conn:
                with conn.cursor() as curs:
                    cycle_id = self.load_forecast_cycle(curs)
                    self.load_cycle_hour(curs, cycle_id)
                    curs.execute(raster_sql)
        except Exception as e:
            logging.exception('Error loading raster into db %s' % e)
            raise
        finally:
            if conn:
                conn.close()

        logging.info('Loaded raster into db')

    def load_forecast_cycle(self, cursor):
        query = """
        WITH upsert AS (
            INSERT INTO forecast_cycles (datetime)
            VALUES (%(datetime)s)
            ON CONFLICT (datetime) DO NOTHING
            RETURNING id
        )
        SELECT * FROM upsert
        UNION 
            SELECT id FROM forecast_cycles 
            WHERE datetime=%(datetime)s
        """
        cursor.execute(query, { 'datetime': self.metadata['cycle_datetime'] })
        return cursor.fetchone()[0]

    
    def load_cycle_hour(self, cursor, cycle_id):
        query = """
        INSERT INTO cycle_hours (key, hour, cycle_id)
        VALUES (%(key)s, %(hour)s, %(cycle_id)s)
        """
        cursor.execute(query, {
            'key': self.cycle_hour_key,
            'hour': int(self.metadata['forecast_hour']),
            'cycle_id': cycle_id
        })


    def _get_raster_info(self):
        logging.info('Getting raster info')
        # https://gdal.org/programs/gdalinfo.html
        info = gdal.Info(self.filename, format='json')
        bands = list(filter(band_filter, info['bands']))
        if len(bands) != len(SCALAR_BANDS):
            logging.warn('Missing raster bands')

        logging.info('Raster info: bands=%s' %
                     [b['metadata']['']['GRIB_ELEMENT'] for b in bands])
        return bands

    def _translate_raster(self, bands):
        logging.info('Translating raster')
        new_filename = os.path.join(self.tmpdir, 'gfs.tif')
        options = ' '.join([
            '-of Gtiff',                        # output GeoTIFF
            '-ot Float32',                      # convert to 32 bit float
            '-projwin -180 85.06 180 -85.06',   # clip to mercator projection
                                                # select output bands
            ' '.join([f'-b {band["band"]}' for band in bands])
        ])
        # https://gdal.org/programs/gdal_translate.html
        gdal.Translate(new_filename, self.filename, options=options)
        logging.info('Translation successful')
        self.filename = new_filename

    def _reproject_raster(self):
        logging.info('Reprojecting raster')
        options = ' '.join([
            '-t_srs EPSG:3857',     # set target spatial reference
                                    # set georeferenced extents of output file
            '-te -20037508.34 -20037508.34 20037508.34 20037508.34',
            '-r cubicspline',       # resample method
            '-ts 1800 1800'         # set pixel height and width
        ])
        # https://gdal.org/programs/gdalwarp.html
        new_filename = os.path.join(self.tmpdir, self.cycle_hour_key)
        gdal.Warp(new_filename, self.filename, options=options)
        logging.info('Reprojection successful')
        self.filename = new_filename
 
    def _generate_raster_sql(self):
        logging.info('Generating raster SQL')
        
        cmd = [
            'raster2pgsql',         # https://postgis.net/docs/using_raster_dataman.html#RT_Raster_Loader
            '-s', '3857',           # use srid 3857
            '-I',                   # create spatial index
            '-C',                   # use standard raster contraints
            '-F',                   # include filename as column, used to index forecast hour
            '-n', 'cycle_hour_key', # name the filename column
            '-t', 'auto',           # cut raster into appropriately sized tile
            '-a',                   # append data to table
            self.filename,          # input raster file
            RASTER_TABLE,           # destination table name
        ]
        try:
            result = subprocess.run(cmd,
                                    check=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            logging.info('Generated raster SQL')
            return result.stdout
        except subprocess.CalledProcessError as e:
            logging.exception('Unable to generate raster SQL: %s' % e)
            raise

def parse_object_key(object_key):
    pattern = r'gfs\.(\d{8})/(\d{2})/atmos/gfs\.t(\d{2})z\.pgrb2\.0p25\.f(\d{3})$'
    match = re.match(pattern, object_key)
    if not match:
        return None
    
    YYYYMMDD = match.group(1)
    CC = match.group(2)
    FFF = match.group(4)
    year = YYYYMMDD[:4]
    month = YYYYMMDD[4:6]
    day = YYYYMMDD[6:8]

    return {
        'cycle_datetime': datetime(int(year), int(month), int(day), int(CC)),
        'forecast_hour': FFF
    }

def parse_record(record):
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    metadata = parse_object_key(key)
    return (bucket, key, metadata)

def process_message(message):
    body = json.loads(message.get('Body', {}))
    body_message = json.loads(body.get('Message', {}))

    for record in body_message.get('Records', []):
        bucket, key, metadata = parse_record(record)
        if bucket and key and metadata:
            with GFSSource(bucket, key, metadata) as gfs_source:
                gfs_source.etl()

def poll():
    queue_url = sqs.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']

    while True:
        # get messages from queue
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )
        if 'Messages' in response:
            for message in response['Messages']:
                try:
                    process_message(message)
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except:
                    logging.exception('Failed to process %s' % message['MessageId'])
                    raise
    
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(module)s][%(levelname)s] %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            RotatingFileHandler(
                'debug.log',
                mode='a',
                maxBytes=5*1024*1024,
                backupCount=5,
            ),
            logging.StreamHandler()
        ]
    )

    parser = argparse.ArgumentParser(description='Process GFS data')
    parser.add_argument('target', type=str, help='"poll", or gfs object key')
    args = parser.parse_args()

    if args.target == 'poll':
        poll()
    else:
        bucket = 'noaa-gfs-bdp-pds'
        key = args.target
        metadata = parse_object_key(key)
        if bucket and key and metadata:
            with GFSSource(bucket, key, metadata) as gfs_source:
                gfs_source.etl()
