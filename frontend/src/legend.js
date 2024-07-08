import { layers } from "./layers";

L.Control.Legend = L.Control.extend({
    getSrc: function(layer) {
        return `${this.options.baseUrl}/${layers[layer]}.png`;
    },

    onAdd: function(map) {
        var img = L.DomUtil.create('img');
        img.id = 'leaflet-legend';
        img.style.border = '1px solid gray';
        img.src = this.getSrc(this.options.defaultLayer);

        map.on('baselayerchange', function(ev) {
            var img = document.getElementById('leaflet-legend');
            img.src = this.getSrc(ev.name);
        }.bind(this))

        return img;
    },
})

L.control.legend = function(opts) {
    return new L.Control.Legend(opts);
}
