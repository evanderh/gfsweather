#!/usr/bin/env python

import os
import re
import logging
import shutil
import json
import tempfile
import subprocess
import argparse
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

from osgeo import gdal
import boto3
from botocore import exceptions
import psycopg2
import dotenv

environment = os.getenv('ENV', 'development')
if environment == 'production':
    dotenv.load_dotenv('.env.production.local')
else:
    dotenv.load_dotenv('.env.development')
DATABASE_URI = os.getenv('DATABASE_URI')

QUEUE_NAME = 'gfsweather'
BUCKET_NAME = 'gfs-velocity'
RASTER_TABLE = 'gfs.rasters'
FORECAST_LIMIT = 48
RASTER_BANDS = [
    {
        'element': 'TMP',
        'layer': '2-HTGL',
    }, {
        'element': 'PRATE',
        'layer': '0-SFC',
    }, {
        'element': 'TCDC',
        'layer': '0-EATM',
    }, {
        'element': 'PRMSL',
        'layer': '0-MSL',
    }, {
        'element': 'RH',
        'layer': '2-HTGL',
    }
]

s3 = boto3.client('s3')
sqs = boto3.client('sqs')


class GFSSource():
    def __init__(self, bucket, key, metadata):
        self.bucket = bucket
        self.object_key = key

        self.cycle_datetime = metadata['cycle_datetime']
        self.forecast_hour = metadata['forecast_hour']
        self.cycle_key = f'{self.cycle_datetime}+{self.forecast_hour}'
    
    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filename = os.path.join(self.tmpdir, 'gfs.grib')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tmpdir)

    def etl(self):
        if (int(self.forecast_hour) > FORECAST_LIMIT):
            logging.info('Ignoring forecast_hour=%s' % self.forecast_hour)
            return

        logging.info('Starting ETL: %s' % self.object_key)
        self.extract()

        raster_sql = self.transform_raster()
        velocity_json = self.transform_velocity()
        self.load_raster(raster_sql)
        self.load_1p00(velocity_json)

        logging.info('ETL complete: %s' % self.object_key)

    def extract(self):
        try:
            logging.info('Downloading')
            s3.download_file(self.bucket, self.object_key, self.filename)
        except exceptions.ClientError as e:
            logging.error("Unable to download: %s" % e)
            raise

    def transform_raster(self):
        logging.info('Filtering raster')
        tmp_filename = os.path.join(self.tmpdir, 'tmp_raster.tif')
        filter_grib(tmp_filename, self.filename, self.forecast_hour, RASTER_BANDS)

        logging.info('Reprojecting raster')
        output_filename = os.path.join(self.tmpdir, self.cycle_key)
        warp_grib(output_filename, tmp_filename, 1800, 1800)

        logging.info('Generating raster SQL')
        return generate_raster_sql(output_filename)

    def transform_velocity(self):
        ugrd = self.transform_velocity_element('UGRD')
        vgrd = self.transform_velocity_element('VGRD')

        result_filename = os.path.join(self.tmpdir, 'result.json')
        with open(result_filename, 'w') as f:
            json.dump([ugrd, vgrd], f)

        return result_filename

    def transform_velocity_element(self, grib_element):
        logging.info('Filtering %s' % grib_element)
        band = [{
            'element': grib_element,
            'layer': '10-HTGL',
        }]
        tmp_filename = os.path.join(self.tmpdir, 'tmp_velocity.tif')
        filter_grib(tmp_filename, self.filename, self.forecast_hour, band)

        logging.info('Downsampling %s' % grib_element)
        downsample_filename = os.path.join(self.tmpdir, 'downsampled.tif')
        warp_grib(downsample_filename, tmp_filename, 360, 181, reproject=False)

        logging.info('Generating %s data' % grib_element)
        data_filename = os.path.join(self.tmpdir, 'velocity_data.json')
        generate_velocity_data(data_filename, downsample_filename)

        logging.info('Generating %s metadata' % grib_element)
        metadata = generate_velocity_metadata(downsample_filename)

        with open(data_filename, 'r') as f:
            return {
                'header': metadata,
                'data': [ round(n, 2) for n in json.loads(f.read()) ],
            }

    def load_raster(self, raster_sql):
        try:
            conn = psycopg2.connect(DATABASE_URI)
            with conn:
                with conn.cursor() as curs:
                    logging.info('Loading raster into db')
                    cycle_id = insert_forecast_cycle(curs,
                                                     self.cycle_datetime)
                    insert_cycle_hour(curs,
                                      self.cycle_key,
                                      self.forecast_hour,
                                      cycle_id)
                    curs.execute(raster_sql)

                    hours = select_all_cycle_hours(curs, cycle_id)
                    if set(hours) == set(range(FORECAST_LIMIT + 1)):
                        update_forecast_cycle(curs, cycle_id)
                        delete_previous_cycles(curs, cycle_id)
        except Exception as e:
            logging.exception('Error loading raster into db %s' % e)
            raise
        finally:
            if conn:
                conn.close()

    def load_1p00(self, velocity_json):
        datetime = self.cycle_datetime + timedelta(hours=int(self.forecast_hour))
        object_name = f'{datetime.isoformat()[:13]}.json'
        try:
            s3.upload_file(velocity_json, BUCKET_NAME, object_name)
        except exceptions.ClientError as e:
            logging.exception('Unable to upload velocity to S3: %s' % e)
            raise

def get_band_info(filename, forecast_hour, filter_bands):
    # https://gdal.org/programs/gdalinfo.html
    info = gdal.Info(filename, format='json')
    forecast_seconds = int(forecast_hour) * 3600

    result = []
    for filter_band in filter_bands:
        def find_band(band):
            metadata = band['metadata']['']
            return (filter_band['element'] == metadata['GRIB_ELEMENT'] and
                    filter_band['layer'] == metadata['GRIB_SHORT_NAME'] )

        item = next(filter(find_band, info['bands']))
        result.append(item)

    return result

def filter_grib(dest_file, src_file, forecast_hour, filter_bands):
    bands = get_band_info(src_file, forecast_hour, filter_bands)
    logging.info('Filter found bands=%s' %
                 [b['metadata']['']['GRIB_ELEMENT'] for b in bands])

    options = ' '.join([
        '-of Gtiff',                        # output GeoTIFF
        '-ot Float32',                      # convert to 32 bit float
        '-projwin -180 85.06 180 -85.06',   # clip to mercator projection
                                            # select output bands
        ' '.join([f'-b {band["band"]}' for band in bands])
    ])
    # https://gdal.org/programs/gdal_translate.html
    gdal.Translate(dest_file, src_file, options=options)

def warp_grib(dest_file, src_file, xres, yres, reproject=True):
    options = [
        '-r cubicspline',           # resample method
        '-ts', str(xres), str(yres) # set pixel height and width
    ]
    if reproject:
        options.extend([
            '-t_srs EPSG:3857',     # set target spatial reference
            '-te',                  # set georeferenced extents of output file
            '-20037508.34 -20037508.34 20037508.34 20037508.34'
        ])

    options = ' '.join(options)
    # https://gdal.org/programs/gdalwarp.html
    gdal.Warp(dest_file, src_file, options=options)

def generate_raster_sql(src_file):
    cmd = [
        'raster2pgsql',         # https://postgis.net/docs/using_raster_dataman.html#RT_Raster_Loader
        '-s', '3857',           # use srid 3857
        '-C',                   # use standard raster contraints
        '-k',
        '-F',                   # include filename as column, used to index forecast hour
        '-n', 'cycle_hour_key', # name the filename column
        '-t', 'auto',           # cut raster into appropriately sized tile
        '-a',                   # append data to table
        src_file,               # input raster file
        RASTER_TABLE,           # destination table name
    ]
    try:
        result = subprocess.run(cmd,
                                check=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.exception('Unable to generate raster SQL: %s' % e)
        raise

def generate_velocity_data(dest_file, src_file):
    cmd = [
        'gtiff2json',
        src_file,
        '-o', dest_file
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logging.exception('Unable to generate velocity json: %s' % e)
        raise

def generate_velocity_metadata(src_file):
    # grib reference: https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/

    info = gdal.Info(src_file, format='json')
    metadata = info['bands'][0]['metadata']['']

    return {
        'scanMode': '0',
        'refTime': datetime.fromtimestamp(int(metadata['GRIB_REF_TIME'])).isoformat()+'Z',
        'forecastTime': int(metadata['GRIB_FORECAST_SECONDS']) / 3600,
        'parameterCategory': metadata['GRIB_PDS_TEMPLATE_NUMBERS'][0],
        'parameterNumber':   metadata['GRIB_PDS_TEMPLATE_NUMBERS'][2],
        'nx': info['size'][0],
        'ny': info['size'][1],
        'lo1': -180.0,
        'la1': 90.0,
        'dx': 1.0,
        'dy': 1.0
    }


def insert_forecast_cycle(cursor, datetime):
    query = """
    WITH upsert AS (
        INSERT INTO gfs.forecast_cycles (datetime, is_complete)
        VALUES (%(datetime)s, false)
        ON CONFLICT (datetime) DO NOTHING
        RETURNING id
    )
    SELECT * FROM upsert
    UNION 
        SELECT id FROM gfs.forecast_cycles 
        WHERE datetime=%(datetime)s
    """
    cursor.execute(query, { 'datetime': datetime })
    result = cursor.fetchone()
    return result[0] if result else None

def insert_cycle_hour(cursor, key, hour, cycle_id):
    query = """
    INSERT INTO gfs.cycle_hours (key, hour, cycle_id)
    VALUES (%(key)s, %(hour)s, %(cycle_id)s)
    ON CONFLICT (key) DO NOTHING
    """
    cursor.execute(query, {
        'key': key,
        'hour': hour,
        'cycle_id': cycle_id
    })

def select_all_cycle_hours(cursor, cycle_id):
    query = """
    SELECT hour FROM gfs.cycle_hours
    WHERE cycle_id=%(cycle_id)s
    """
    cursor.execute(query, {
        'cycle_id': cycle_id
    })
    result = cursor.fetchall()
    return [r[0] for r in result]

def update_forecast_cycle(cursor, cycle_id):
    query = """
    UPDATE gfs.forecast_cycles SET is_complete = true
    WHERE id=%(cycle_id)s
    """
    cursor.execute(query, {
        'cycle_id': cycle_id
    })

def delete_previous_cycles(cursor, cycle_id):
    query = """
    DELETE FROM gfs.forecast_cycles
    WHERE datetime < (
        SELECT datetime FROM gfs.forecast_cycles
        WHERE id=%(cycle_id)s
    )
    RETURNING id
    """
    cursor.execute(query, { 'cycle_id': cycle_id })
    result = cursor.fetchall()
    return [r[0] for r in result]

def parse_object_key(object_key):
    pattern = r'gfs\.(\d{8})/(\d{2})/atmos/gfs\.t(\d{2})z\.pgrb2\.0p25\.f(\d{3})$'
    match = re.match(pattern, object_key)
    if not match:
        return None
    
    YYYYMMDD = match.group(1)
    hour = match.group(2)
    fff = match.group(4)
    year = YYYYMMDD[:4]
    month = YYYYMMDD[4:6]
    day = YYYYMMDD[6:8]

    return {
        'cycle_datetime': datetime(int(year), int(month), int(day), int(hour)),
        'forecast_hour': fff,
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
        logging.info('Polling...')
        # get messages from queue
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
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
