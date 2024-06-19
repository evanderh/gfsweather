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

from layers import LAYERS
from legend import generate_legend

environment = os.getenv('ENV', 'development')
if environment == 'production':
    dotenv.load_dotenv('../server/.env.production.local')
else:
    dotenv.load_dotenv('../server/.env.development.local')
DATABASE_URI = os.getenv('DATABASE_URI')

FORECAST_LIMIT = 24
NPROCESSES = 4
QUEUE_NAME = 'gfsweather'
LAYERS_PATH = '../layers'

s3 = boto3.client('s3')
sqs = boto3.client('sqs')

class GFSSource():
    def __init__(self, bucket, key, metadata):
        self.bucket = bucket
        self.object_key = key
        self.cycle_datetime = metadata['cycle_datetime']
        self.forecast_hour = metadata['forecast_hour']
    
    def __enter__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.filename = os.path.join(self.tmpdir, 'gfs.grib')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.tmpdir)

    def create_dirs(self):
        self.cycle_path = os.path.join(LAYERS_PATH,
                                       self.cycle_datetime.isoformat()[:13])
        if not os.path.exists(self.cycle_path):
            os.mkdir(self.cycle_path)

        forecast_dt = self.cycle_datetime + timedelta(hours=int(self.forecast_hour))
        self.forecast_path = os.path.join(self.cycle_path,
                                          forecast_dt.isoformat()[:13])
        if not os.path.exists(self.forecast_path):
            os.mkdir(self.forecast_path)

    def etl(self):
        cycle = self.cycle_datetime.isoformat()[:13]
        logging.info('Processing %s:%s' % (cycle, self.forecast_hour))

        if (int(self.forecast_hour) >= FORECAST_LIMIT):
            logging.info('Forecast out of range')
            return

        self.create_dirs()
        self.extract()

        velocity_json = self.transform_velocity()
        self.load_velocity(velocity_json)

        self.transform_rasters()
        self.load_rasters()

        logging.info('ETL complete: %s' % self.object_key)

    def extract(self):
        if os.path.exists(self.filename):
            return
        try:
            logging.info('Downloading')
            s3.download_file(self.bucket, self.object_key, self.filename)
        except exceptions.ClientError as e:
            logging.error("Unable to download: %s" % e)
            raise

    def transform_velocity(self):
        ugrd = self.transform_velocity_element('UGRD')
        vgrd = self.transform_velocity_element('VGRD')

        result_filename = os.path.join(self.tmpdir, 'wind_velocity.json')
        with open(result_filename, 'w') as f:
            json.dump([ugrd, vgrd], f)

        return result_filename

    def transform_velocity_element(self, grib_element):
        logging.info('Filtering %s' % grib_element)
        band = [{
            'element': grib_element,
            'layer': '10-HTGL',
            'pdtn': '0',
        }]
        tmp_filename = os.path.join(self.tmpdir, 'tmp_velocity.tif')
        filter_raster(tmp_filename, self.filename, band)

        logging.info('Downsampling %s' % grib_element)
        downsample_filename = os.path.join(self.tmpdir, 'downsampled.tif')
        warp_raster(downsample_filename, tmp_filename, 360, 181, reproject=False)

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

    def load_velocity(self, velocity_json):
        dest_path = os.path.join(self.forecast_path, 'wind_velocity.json')
        shutil.move(velocity_json, dest_path)

    def transform_rasters(self):
        for layer in LAYERS:
            bandname = layer['name']
            logging.info('Filtering %s' % bandname)
            filtered_filename = os.path.join(self.tmpdir, f'{bandname}.filtered.tif')
            filter_raster(filtered_filename,
                          self.filename,
                          [layer['band']],
                          tuple(map(str, layer['scale'])))

            logging.info('Reprojecting %s' % bandname)
            projected_filename = os.path.join(self.tmpdir, f'{bandname}.projected.tif')
            warp_raster(projected_filename, filtered_filename, 6400, 6400)

            color_table_path = os.path.join(self.tmpdir, 'color_table.txt')
            with open(color_table_path, 'w') as f:
                scale = layer['scale']
                scale_range = scale[1] - scale[0]
                bit_value = scale_range / 255
                for row in layer['color_scale']:
                    scaled_value = round((row[0] - scale[0]) / bit_value)
                    scaled_row = ' '.join([str(scaled_value), *map(str, row[1:])])
                    f.write(scaled_row + '\n')

            logging.info('Shading %s' % bandname)
            shaded_filename = os.path.join(self.tmpdir, f'{bandname}.shaded.tif')
            gdal.DEMProcessing(shaded_filename,
                               projected_filename,
                               'color-relief',
                               colorFilename=color_table_path)

            tiles_dir = os.path.join(self.forecast_path, bandname)
            generate_tiles(tiles_dir, shaded_filename, NPROCESSES, '2-6')

            legend_path = os.path.join(LAYERS_PATH, f'{bandname}.png')
            generate_legend(layer, legend_path)

    def load_rasters(self):
        try:
            conn = psycopg2.connect(DATABASE_URI)
            with conn:
                with conn.cursor() as curs:
                    cycle_id = insert_forecast_cycle(curs,
                                                     self.cycle_datetime)
                    insert_forecast_hour(curs,
                                         self.forecast_hour,
                                         cycle_id)

                    hours = select_all_forecast_hours(curs, cycle_id)
                    if set(hours) == set(range(FORECAST_LIMIT)):
                        update_forecast_cycle(curs, cycle_id)
                        prev_cycle_dts = delete_previous_cycles(curs, cycle_id)
                        for cycle_dt in prev_cycle_dts:
                            cycle_path = os.path.join(LAYERS_PATH,
                                                      cycle_dt.isoformat()[:13])
                            shutil.rmtree(cycle_path)

        except Exception as e:
            logging.exception('Error loading raster into db %s' % e)
            raise
        finally:
            if conn:
                conn.close()

def get_band_info(filename, filter_bands):
    # https://gdal.org/programs/gdalinfo.html
    info = gdal.Info(filename, format='json')

    result = []
    for filter_band in filter_bands:
        def find_band(band):
            metadata = band['metadata']['']
            return (filter_band['element'] == metadata['GRIB_ELEMENT'] and
                    filter_band['layer'] == metadata['GRIB_SHORT_NAME'] and
                    filter_band['pdtn'] == metadata['GRIB_PDS_PDTN'])

        item = next(filter(find_band, info['bands']))
        result.append(item)

    return result

def filter_raster(dest_file, src_file, filter_bands, scale=None):
    bands = get_band_info(src_file, filter_bands)
    logging.info('Filter found bands=%s' %
                 [b['metadata']['']['GRIB_ELEMENT'] for b in bands])

    options = ' '.join([
        '-a_nodata', 'none',
        '-of Gtiff',    # output GeoTIFF
                        # select output bands
        ' '.join([f'-b {band["band"]}' for band in bands])
    ])
    if scale:
        options = ' '.join([
            options,
            '-ot', 'Byte',
            '-scale', *scale
        ])

    # https://gdal.org/programs/gdal_translate.html
    gdal.Translate(dest_file, src_file, options=options)

def warp_raster(dest_file, src_file, xres, yres, reproject=True):
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

def generate_tiles(dest_dir, src_file, processes, zoom):
    cmd = [
        'gdal2tiles.py',
        '--processes', str(processes),
        '-z', zoom,
        src_file,
        dest_dir,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logging.exception('Unable to generate velocity json: %s' % e)
        raise

def insert_forecast_cycle(cursor, datetime):
    query = """
    WITH upsert AS (
        INSERT INTO forecast_cycles (datetime, is_complete)
        VALUES (%(datetime)s, false)
        ON CONFLICT (datetime) DO NOTHING
        RETURNING id
    )
    SELECT * FROM upsert
    UNION 
        SELECT id FROM forecast_cycles 
        WHERE datetime=%(datetime)s
    """
    cursor.execute(query, { 'datetime': datetime })
    result = cursor.fetchone()
    return result[0] if result else None

def insert_forecast_hour(cursor, hour, cycle_id):
    query = """
    INSERT INTO forecast_hours (hour, cycle_id)
    VALUES (%(hour)s, %(cycle_id)s)
    ON CONFLICT (hour, cycle_id) DO NOTHING
    """
    cursor.execute(query, {
        'hour': hour,
        'cycle_id': cycle_id
    })

def select_all_forecast_hours(cursor, cycle_id):
    query = """
    SELECT hour FROM forecast_hours
    WHERE cycle_id=%(cycle_id)s
    """
    cursor.execute(query, {
        'cycle_id': cycle_id
    })
    result = cursor.fetchall()
    return [r[0] for r in result]

def update_forecast_cycle(cursor, cycle_id):
    query = """
    UPDATE forecast_cycles SET is_complete = true
    WHERE id=%(cycle_id)s
    """
    cursor.execute(query, {
        'cycle_id': cycle_id
    })

def delete_previous_cycles(cursor, cycle_id):
    query = """
    DELETE FROM forecast_cycles
    WHERE datetime < (
        SELECT datetime FROM forecast_cycles
        WHERE id=%(cycle_id)s
    )
    RETURNING datetime
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
