#!/usr/bin/env python

from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession
)

import uvicorn
from fastapi import Depends, FastAPI, Response
from database import get_session

app = FastAPI()

@app.get(
    "/tiles/{z}/{x}/{y}.png",
    responses = { 200: { "content": {"image/png": {}} } },
)
async def tiles(
    z: int,
    x: int,
    y: int,
    session: AsyncSession = Depends(get_session)
):
    stmt = text(f'''
SELECT
    ST_AsPNG(ST_Resize(ST_Union(ST_ColorMap(
        r2,
        '60.0  158,1,66
        40.0  213,62,79
        35.0  244,109,67
        30.0  253,174,97
        25.0  254,224,139
        20.0   255,255,191
        15.0   230,245,152
        10.0 171,221,164
        5.0 102,194,165
        0.0 50,136,189
        -80.0 94,79,162'
    )), 256, 256, 'CubicSpline'))
FROM (
    SELECT
        ST_Clip(
            ST_Resample(
                ST_Union(r),
                256, 256,
                ST_Xmin(ST_TileEnvelope({z},{x},{y})),
                ST_YMax(ST_TileEnvelope({z},{x},{y})),
                0, 0,
                'CubicSpline'
            ),
            ST_TileEnvelope({z},{x},{y})
        ) as r2
    FROM (
        SELECT
            ST_Clip(
                rast,
                ST_Expand(ST_TileEnvelope({z},{x},{y}), 16000)
            )
            as r
        FROM
            temperature
        WHERE ST_Intersects(rast, ST_Expand(ST_TileEnvelope({z},{x},{y}), 16000))
    )
)
    ''')
    result = await session.scalar(stmt)
    return Response(content=result, media_type='image/png')

if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        reload=True,
    )
