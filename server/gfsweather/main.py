#!/usr/bin/env python

import io
import uvicorn
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session
from datetime import datetime
from PIL import Image, ImageDraw
from geoalchemy2.functions import (
    ST_AsPNG,
    ST_Resize,
    ST_Union,
    ST_ColorMap,
    ST_Clip,
    ST_Resample,
    ST_XMin,
    ST_YMax,
    ST_TileEnvelope,
    ST_Expand,
    ST_Intersects,
    ST_Band
)
from database import get_session
from models import Raster, CycleHour, ForecastCycle

app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://localhost:8000'
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.get("/forecast_cycle")
def cycle_datetime(session: Session = Depends(get_session)):
    start_datetime, hour_limit = session.execute(
        select(ForecastCycle.datetime, func.max(CycleHour.hour))
        .join(ForecastCycle, CycleHour.cycle_id == ForecastCycle.id)
        .where(ForecastCycle.is_complete == True)
        .group_by(ForecastCycle.datetime)
    ).first()
    return {
        'startDatetime': start_datetime,
        'hourLimit': hour_limit
    }


@app.get(
    "/legend.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def legend():
    color_table = temperature_color_scale
    
    # Define the dimensions of the legend image
    legend_width = 100
    legend_height = 300
    color_bar_width = 20
    num_colors = len(color_table)
    segment_height = legend_height / (num_colors - 1)
    
    # Create a new image with a white background
    legend = Image.new('RGB', (legend_width, legend_height), (255, 255, 255))
    draw = ImageDraw.Draw(legend)

    for i in range(legend_height):
        # Determine which segment we're in and the local position within the segment
        segment_index = int(i // segment_height)
        segment_pos = (i % segment_height) / segment_height
        
        # Interpolate between the colors of the current segment
        if segment_index < num_colors - 1:
            start_color = color_table[segment_index]
            end_color = color_table[segment_index + 1]
            color = interpolate_color(start_color, end_color, segment_pos)
            draw.line([(0, i), (color_bar_width, i)], fill=color)

    # Add color band labels
    for idx, entry in enumerate(color_table):
        if (idx == 0 or idx == num_colors - 1):
            continue
        c = f"{int(entry[0])}°C"
        f = f"{int(entry[0]*1.8 + 32)}°F"
        fill = (0, 0, 0)
        y_position = int(idx * segment_height) - 5
        draw.text((color_bar_width + 30, y_position),
                  c, fill=fill, anchor='rt')
        draw.text((color_bar_width + 42, y_position),
                  "/", fill=fill, anchor='rt')
        draw.text((color_bar_width + 75, y_position),
                  f, fill=fill, anchor='rt')
 
    # Save the image to a BytesIO object
    img_io = io.BytesIO()
    legend.save(img_io, 'PNG')
    img_io.seek(0)
    
    return Response(content=img_io.getvalue(), media_type='image/png') 


temperature_color_scale = [
    [60.0, 158, 1, 66], 
    [40.0, 213, 62, 79], 
    [35.0, 244, 109, 67], 
    [30.0, 253, 174, 97], 
    [25.0, 254, 224, 139], 
    [20.0, 255, 255, 191], 
    [15.0, 230, 245, 152], 
    [10.0, 171, 221, 164], 
    [ 5.0, 102, 194, 165], 
    [ 0.0, 50, 136, 189], 
    [-80.0, 94, 79, 162]
]

def make_color_map(scale):
    def makeRow(row):
        return ','.join([str(n) for n in row])
    rows = [makeRow(row) for row in scale]
    return '\n'.join(rows)


def interpolate_color(start_color, end_color, t):
    r = int(start_color[1] + (end_color[1] - start_color[1]) * t)
    g = int(start_color[2] + (end_color[2] - start_color[2]) * t)
    b = int(start_color[3] + (end_color[3] - start_color[3]) * t)
    return (r, g, b)


@app.get(
    "/{layer}/{date}/{z}/{x}/{y}.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def tiles(
    layer: str, date: str, z: int, x: int, y: int,
    session: Session = Depends(get_session)
):
    colormap = None
    band = None
    if layer == 'temperature':
        colormap = make_color_map(temperature_color_scale)
        band = 1
    elif layer == 'cloudcover':
        colormap = 'bluered'
        band = 3

    dt = datetime.fromisoformat(date)
    hours_from_start = func.extract('epoch', func.age(dt, ForecastCycle.datetime)) / 3600

    cycle_hour_key_subquery = (
        select(CycleHour.key)
        .join(ForecastCycle, CycleHour.cycle_id == ForecastCycle.id)
        .where(
            ForecastCycle.is_complete == True,
            CycleHour.hour == hours_from_start
        )
        .scalar_subquery()
    )

    tile_margin = 22500
    selected_rasters_subquery = (
        select(
            ST_Clip(
                ST_Band(Raster.rast, band),
                ST_Expand(ST_TileEnvelope(z, x, y), tile_margin)
            ).label('rasters')
        ).where(
            ST_Intersects(Raster.rast, ST_Expand(ST_TileEnvelope(z, x, y), tile_margin)),
            Raster.cycle_hour_key == cycle_hour_key_subquery
        ).subquery()
    )

    resampled_rasters_subquery = (
        select(
            ST_Clip(
                ST_Resample(
                    ST_Union(selected_rasters_subquery.c.rasters),
                    256, 256,
                    ST_XMin(ST_TileEnvelope(z, x, y)),
                    ST_YMax(ST_TileEnvelope(z, x, y)),
                    0, 0,
                    'CubicSpline'
                ),
                ST_TileEnvelope(z, x, y)
            ).label('rasters')
        ).subquery()
    )

    stmt = (
        select(
            ST_AsPNG(
                ST_Resize(
                    ST_Union(
                        ST_ColorMap(
                            resampled_rasters_subquery.c.rasters,
                            text(f"'{colormap}'")
                        )
                    ),
                    256, 256, 'CubicSpline'
                )
            )
        )
    )

    result = session.execute(stmt).scalar()
    return Response(content=bytes(result), media_type='image/png')


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        reload=True,
    )
