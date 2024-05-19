import os
import boto3
import json
import re
import logging
import shutil
import tempfile
import psycopg2
import subprocess
from logging.handlers import RotatingFileHandler
from botocore.exceptions import BotoCoreError, ClientError
from osgeo import gdal

QUEUE_NAME = 'gfsweather'
RASTER_TABLE = 'public.rasters'
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

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
        self.raster_key = metadata['forecast_hour'] 
    
    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
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
            filename = os.path.join(self.tmpdir, 'gfs.grib')
            s3.download_file(self.bucket, self.key, filename)
            logging.info('Download successful')
        except ClientError as e:
            logging.error("Unable to download: %s" % e)
            raise

    def transform(self):
        bands = self._get_raster_info()
        translated_raster_filename = self._translate_raster(bands)
        raster_filename = self._reproject_raster(translated_raster_filename)
        return self._generate_raster_sql(raster_filename)

    def load(self, raster_sql):
        logging.info('Loading raster into db')
        try:
            connection = psycopg2.connect(**DB_PARAMS)
            cursor = connection.cursor()
            cursor.execute(raster_sql)
            connection.commit()
            logging.info('Loaded raster into db')
        except Exception as e:
            logging.exception('Error loading raster into db')
            if connection:
                connection.rollback()
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

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
        return new_filename

    def _reproject_raster(self, raster_filename):
        logging.info('Reprojecting raster')
        options = ' '.join([
            '-t_srs EPSG:3857',     # set target spatial reference
                                    # set georeferenced extents of output file
            '-te -20037508.34 -20037508.34 20037508.34 20037508.34',
            '-r cubicspline',       # resample method
            '-ts 1800 1800'         # set pixel height and width
        ])
        # https://gdal.org/programs/gdalwarp.html
        new_filename = os.path.join(self.tmpdir, self.raster_key)
        gdal.Warp(new_filename, raster_filename, options=options)
        logging.info('Reprojection successful')
        return new_filename
 
    def _generate_raster_sql(self, raster_filename):
        logging.info('Generating raster SQL')
        
        cmd = [
            'raster2pgsql',     # https://postgis.net/docs/using_raster_dataman.html#RT_Raster_Loader
            '-s', '3857',       # use srid 3857
            '-I',               # create spatial index
            '-C',               # use standard raster contraints
            '-F',               # include filename as column, used to index forecast hour
            '-n raster_key'     # name the filename column
            '-t', 'auto',       # cut raster into appropriately sized tile
            '-a',               # append data to table
            raster_filename,    # input raster file
            RASTER_TABLE,       # destination table name
        ]
        try:
            result = subprocess.run(cmd,
                                    check=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logging.exception('Unable to generate raster SQL: %s' % e)

        logging.info('Generated raster SQL')
        return result.stdout


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
        'year': year,
        'month': month,
        'day': day,
        'cycle_runtime': CC,
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

def main():
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

    main()
