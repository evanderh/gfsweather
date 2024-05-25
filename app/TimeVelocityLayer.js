L.TimeDimension.Layer.VelocityLayer = L.TimeDimension.Layer.extend({

    initialize: function(options) {
        var layer = new L.VelocityLayer(
          options.velocityLayerOptions || {}
        );
        L.TimeDimension.Layer.prototype.initialize.call(this, layer, options);
        this._currentLoadedTime = 0;
        this._currentTimeData = [];
        this._baseURL = this.options.baseURL || null;
    },

    onAdd: function(map) {
        L.TimeDimension.Layer.prototype.onAdd.call(this, map);
        if (this._timeDimension) {
            this._getDataForTime(this._timeDimension.getCurrentTime());
        }
    },

    _onNewTimeLoading: function(ev) {
        this._getDataForTime(ev.time);
        return;
    },

    isReady: function(time) {
        return (this._currentLoadedTime == time);
    },

    _update: function() {
        if (this._currentTimeData && this._currentTimeData.length > 0) {
            this._map.addLayer(this._baseLayer);
            this._baseLayer.setData(this._currentTimeData);
        } else {
            this._map.removeLayer(this._baseLayer);
        }

        return true;
    },

    _getDataForTime: function(time) {
        if (!this._baseURL || !this._map) {
            return;
        }
        var url = this._constructQuery(time);
        var oReq = new XMLHttpRequest();
        oReq.addEventListener("load", (function(xhr) {
            var data = [];
            try {
                var response = xhr.currentTarget.response;
                data = JSON.parse(response);
            } catch(e) {
                console.log("Error parsing API response", e);
            }
            delete this._currentTimeData;
            this._currentTimeData = data;
            console.log(new Date(time).toISOString())
            this._currentLoadedTime = time;
            if (this._timeDimension && time == this._timeDimension.getCurrentTime() && !this._timeDimension.isLoading()) {
                this._update();
            }
            this.fire('timeload', {
                time: time
            });
        }).bind(this));

        oReq.open("GET", url);
        oReq.send();
    },

    _constructQuery: function(time) {
        var datetime = new Date(time);
        var timeParams = `/${datetime.toISOString().slice(0, 13)}.json`;
        var url = this._baseURL + timeParams;
        return url;
    },

});

L.timeDimension.layer.velocityLayer = function(options) {
    return new L.TimeDimension.Layer.VelocityLayer(options);
};
