#!/usr/bin/env python

import uvicorn
from fastapi import Depends, FastAPI, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session
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

@app.get(
    "/tiles/{z}/{x}/{y}.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
def tiles(
    z: int, x: int, y: int,
    session: Session = Depends(get_session)
):
    tile_margin = 22500
    hour = 12

    cycle_hour_key_subquery = (
        select(CycleHour.key)
        .join(ForecastCycle, CycleHour.cycle_id == ForecastCycle.id)
        .where(ForecastCycle.is_complete == True, CycleHour.hour == hour)
        .scalar_subquery()
    )

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
