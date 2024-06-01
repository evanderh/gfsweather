def tmp_legend_text(draw, colormap, segment_height):
    for idx, entry in enumerate(colormap):
        if idx == 0 or idx == len(colormap) - 1:
            continue

        y_position = int(idx * segment_height)
        celcius = int(entry[0])
        farenheit = int(entry[0]*1.8 + 32)

        draw.text((70, y_position),
                   f"{celcius}°C  /  {farenheit}°F",
                   fill=(0, 0, 0),
                   anchor='mm')


def prate_legend_text(draw, colormap, segment_height):
    for idx, entry in enumerate(colormap):
        if idx == 0 or idx == len(colormap) - 1:
            continue

        y_position = int(idx * segment_height)
        mm = float(entry[0]) * 3600
        inch = round(mm*3/64, 3)

        draw.text((70, y_position),
                   f"{inch:.2f} in  /  {mm} mm",
                   fill=(0, 0, 0),
                   anchor='mm')

def pres_legend_text(draw, colormap, segment_height):
    for idx, entry in enumerate(colormap):
        if idx == 0 or idx == len(colormap) - 1:
            continue

        y_position = int(idx * segment_height)
        pressure = int(entry[0]) / 100

        draw.text((70, y_position),
                   f"{pressure:.0f} hPa",
                   fill=(0, 0, 0),
                   anchor='mm')

def percentage_legend_text(text):
    def legend_text(draw, colormap, segment_height):
        for idx, entry in enumerate(colormap):
            y_position = int(idx * segment_height) + (15 if idx==0 else -15)
            draw.text((70, y_position),
                    f"{entry[0]}%  {text}",
                    fill=(0, 0, 0),
                    anchor='mm')

    return legend_text

layers = {
    'TMP': {
        'band': 1,
        'color_scale': [
            [60.0, 158,   1,  66], 
            [40.0, 213,  62,  79], 
            [35.0, 244, 109,  67], 
            [30.0, 253, 174,  97], 
            [25.0, 254, 224, 139], 
            [20.0, 255, 255, 191], 
            [15.0, 230, 245, 152], 
            [10.0, 171, 221, 164], 
            [ 5.0, 102, 194, 165], 
            [ 0.0,  50, 136, 189], 
            [-80.0, 94,  79, 162]
        ],
        'legend_text': tmp_legend_text,
    },
    'PRATE': {
        'band': 2,
        'color_scale': [
            [128/3600, 158,   1,  66], 
            [ 64/3600, 213,  62,  79], 
            [ 32/3600, 244, 109,  67], 
            [ 16/3600, 253, 174,  97], 
            [  8/3600, 254, 224, 139], 
            [  4/3600, 230, 245, 152], 
            [  2/3600, 171, 221, 164], 
            [  1/3600, 102, 194, 165], 
            [0.5/3600,  50, 136, 189], 
            [       0, 223, 223, 223, 0], 
        ],
        'legend_text': prate_legend_text,
    },
    'TCDC': {
        'band': 3,
        'color_scale': [
            [100,  64,  64,  64, 255], 
            [  0, 223, 223, 223,   0], 
        ],
        'legend_text': percentage_legend_text('Cloud Cover'),
    },
    'PRES': {
        'band': 4,
        'color_scale': [
            [104000, 215,48,39],
            [103000, 252,141,89],
            [102000, 254,224,144],
            [101000, 224,243,248],
            [100000, 145,191,219],
            [ 99000, 116,173,209],
            [ 50000,  69,117,180]
        ],
        'legend_text': pres_legend_text,
    },
    'RH': {
        'band': 5,
        'color_scale': [
            [100,  32,  32,  32], 
            [  0, 223, 223, 223], 
        ],
        'legend_text': percentage_legend_text('Humidity'),
    },
}

def get_layer_config(layer):
    if layer in layers:
        config = layers[layer]
        return config['band'], make_color_map(config['color_scale'])
    else:
        raise Exception('no config!')

def make_color_map(scale):
    def makeRow(row):
        return ','.join([str(n) for n in row])
    rows = [makeRow(row) for row in scale]
    return '\n'.join(rows)
