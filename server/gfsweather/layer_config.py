layers = {
    'tmp': {
        'band': 1,
        'color_scale': [
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
        ],
    },
    'prate': {
        'band': 2,
        'color_scale': [
            [0.1,      215,  25,  28],
            [0.01,     253, 174,  97],
            [0.0001,   255, 255, 191],
            [0.00001,  171, 221, 164],
            [0.000001,  43, 131, 186],
            [0,        255, 255, 255] 
        ],
    },
}

blackwhite_color_scale = [
    [100,  64,  64,  64], 
    [ 50, 128, 128, 128],
    [  0, 255, 255, 255], 
]

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
