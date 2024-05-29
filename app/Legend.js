import { layersConfig } from "./LayersConfig";

L.Control.Legend = L.Control.extend({

    options: {
        position: 'topleft',
    },

    onAdd: function(map) {
        var img = L.DomUtil.create('img');
        img.id = 'leaflet-legend';
        img.style.border = '1px solid gray';
        img.src = `${this.options.serverUrl}/TMP/legend.png`;
        console.log(img.src)

        map.on('baselayerchange', function(ev) {
            var img = document.getElementById('leaflet-legend');
            var layer = layersConfig[ev.name];
            img.src = `${this.options.serverUrl}/${layer}/legend.png`
        }.bind(this))

        return img;
    },
})

L.control.legend = function(opts) {
    return new L.Control.Legend(opts);
}
