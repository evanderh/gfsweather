import os
import time
import boto3
import json
import re
import logging
import shutil
import tempfile
from logging.handlers import RotatingFileHandler
from botocore.exceptions import BotoCoreError, ClientError
from osgeo import gdal

QUEUE_NAME = 'gfsweather'

s3 = boto3.client('s3')
sqs = boto3.client('sqs')


SCALAR_BANDS = [
    # (grib element, grib short name)
    ('TMP', '2-HTGL')
]

def make_band_filter(bands):
    def band_filter(band):
        metadata = band['metadata']['']
        for (element, short_name) in bands:
            if (element == metadata['GRIB_ELEMENT'] and
                short_name == metadata['GRIB_SHORT_NAME']):
                return True
        return False
    return band_filter


class GFSSource():
    def __init__(self, bucket, key, metadata):
        self.bucket = bucket
        self.key = key
        self.metadata = metadata
    
    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filename = os.path.join(self.tmpdir, 'gfs.grib')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tmpdir)

    def etl(self):
        logging.info('Starting ETL for %s' % self.key)
        self.extract()
        self.transform()

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
        raster_filename = self._translate_raster(bands)
        raster_filename = self._reproject_raster(raster_filename)


    def _get_raster_info(self):
        logging.info('Getting raster info')
        # https://gdal.org/programs/gdalinfo.html
        info = gdal.Info(self.filename, format='json')
        bands = list(filter(make_band_filter(SCALAR_BANDS), info['bands']))
        if len(bands) != len(SCALAR_BANDS):
            logging.warn('Missing raster bands')

        logging.info('Found bands: %s' %
                     [b['metadata']['']['GRIB_ELEMENT'] for b in bands])
        return bands

    def _translate_raster(self, bands):
        logging.info('Translating raster')
        new_filename = os.path.join(self.tmpdir, f'{self.filename}.tif')

        # https://gdal.org/programs/gdal_translate.html
        # select+convert bands to float32, clip to EPSG:3857 bounds
        band_opts = ' '.join([f'-b {band["band"]}' for band in bands])
        options = f'-of Gtiff -ot Float32 -projwin -180 85.06 180 -85.06 {band_opts}'
        gdal.Translate(new_filename, self.filename, options=options)
        logging.info('Translation successful')
        return new_filename

    def _reproject_raster(self, raster_filename):
        logging.info('Reprojecting raster')
        new_filename = os.path.join(self.tmpdir, f'{self.filename}.3857.tif')
        gdal.Warp(new_filename, raster_filename, options='-t_srs EPSG:3857')
        logging.info('Reprojection successful')
        return new_filename


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
