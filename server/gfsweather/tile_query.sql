-- not used anymore but kept for reference

SELECT
    ST_AsPNG(ST_Resize(ST_Union(ST_ColorMap(
        r2,
        '60.0 158,1,66
        40.0 213,62,79
        35.0 244,109,67
        30.0 253,174,97
        25.0 254,224,139
        20.0 255,255,191
        15.0 230,245,152
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
                ST_Expand(ST_TileEnvelope({z},{x},{y}), 22500)
            )
            as r
        FROM
            rasters
        WHERE ST_Intersects(rast, ST_Expand(ST_TileEnvelope({z},{x},{y}), 22500))
    )
)
