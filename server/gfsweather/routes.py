import io
from datetime import datetime

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
    ST_Band,
)
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw
from fastapi import Depends, Response, APIRouter

from database import get_session
from models import Raster, CycleHour, ForecastCycle
from layer_config import make_color_map, layers


router = APIRouter(prefix='/api')


@router.get("/forecast_cycle")
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


@router.get(
    "/{layer}/{date}/{z}/{x}/{y}.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def tiles(
    layer: str, date: str, z: int, x: int, y: int,
    session: Session = Depends(get_session)
):
    band = layers[layer]['band']
    colormap = make_color_map(layers[layer]['color_scale'])

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


def interpolate_color(start_color, end_color, t):
    r = int(start_color[1] + (end_color[1] - start_color[1]) * t)
    g = int(start_color[2] + (end_color[2] - start_color[2]) * t)
    b = int(start_color[3] + (end_color[3] - start_color[3]) * t)
    return (r, g, b)


@router.get(
    "/{layer}/legend.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def legend(layer: str):
    # Get the color map
    colormap = layers[layer]['color_scale']
    
    # Define the dimensions of the legend image
    legend_width = 120
    legend_height = 300
    color_bar_width = 20
    num_colors = len(colormap)
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
            start_color = colormap[segment_index]
            end_color = colormap[segment_index + 1]
            color = interpolate_color(start_color, end_color, segment_pos)
            draw.line([(0, i), (color_bar_width, i)], fill=color)

    # Add color band labels
    legend_text = layers[layer]['legend_text']
    legend_text(draw, colormap, segment_height)


    # Save the image to a BytesIO object
    img_io = io.BytesIO()
    legend.save(img_io, 'PNG')
    img_io.seek(0)
    
    return Response(content=img_io.getvalue(), media_type='image/png') 
