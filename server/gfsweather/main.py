#!/usr/bin/env python

import uvicorn
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session
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
    ST_Intersects
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
    "/tiles/{d}/{z}/{x}/{y}.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def tiles(
    d: str, z: int, x: int, y: int,
    session: Session = Depends(get_session)
):
    dt = datetime.fromisoformat(d)
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
                Raster.rast,
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
                            text("'60.0 158,1,66\n"
                                "40.0 213,62,79\n"
                                "35.0 244,109,67\n"
                                "30.0 253,174,97\n"
                                "25.0 254,224,139\n"
                                "20.0 255,255,191\n"
                                "15.0 230,245,152\n"
                                "10.0 171,221,164\n"
                                "5.0 102,194,165\n"
                                "0.0 50,136,189\n"
                                "-80.0 94,79,162'")
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
