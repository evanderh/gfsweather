L.TimeDimension.VelocityLayer = L.TimeDimension.Layer.extend({

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
        var date = new Date(time);
        var dateFormatted = date.toISOString().slice(0, 13)

        var path = `/${dateFormatted}/wind_velocity.json`;
        return this._baseURL + path;
    },

});

L.timeDimension.velocityLayer = function(options) {
    return new L.TimeDimension.VelocityLayer(options);
};
