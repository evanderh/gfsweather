import './style.css'
import 'leaflet/dist/leaflet.css';
import 'leaflet-velocity/dist/leaflet-velocity.css';
import 'leaflet-timedimension/dist/leaflet.timedimension.control.css';

import L from 'leaflet';
import 'leaflet-velocity/dist/leaflet-velocity.js';
import 'leaflet-timedimension/dist/leaflet.timedimension.src.withlog.js';
import './TimeLayer.js';
import './TimeVelocityLayer.js';
import './Legend.js';

import { config } from './config.js';

fetch(`${config.SERVER_URL}/forecast_cycle`)
    .then(response => response.json())
    .then(data => {
        let { startDatetime, hourLimit } = data;
        let map = L.map('map', {
            center: [39, -98],
            zoom: 5,
            minZoom: 3,
            maxZoom: 11,
            maxBounds: [[-85, -720], [85, 720]],
            timeDimensionControl: true,
            timeDimensionControlOptions: {
                position: 'bottomleft',
                maxSpeed: 2,
                playerOptions: {
                    transitionTime: 2000,
                },
                timeZones: ["Local"],
                playButton: false,
                speedSlider: false,
            },
            timeDimension: true,
            timeDimensionOptions: {
                timeInterval: `${startDatetime}Z/PT${hourLimit}H`,
                period: "PT1H",
            }
        });

        L.timeDimension.timeLayer = function(layer, options) {
            return new L.TimeDimension.TimeLayer(layer, options);
        };

        var tmpLayer = L.timeDimension.timeLayer(
            L.tileLayer(`${config.SERVER_URL}/tmp/{d}/{z}/{x}/{y}.png`), {
            zIndex: 1,
        }).addTo(map);

        var prateLayer = L.timeDimension.timeLayer(
            L.tileLayer(`${config.SERVER_URL}/prate/{d}/{z}/{x}/{y}.png`), {
            zIndex: 2,
        });

        L.tileLayer('http://localhost:8080/styles/osm-bright/256/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            zIndex: 3,
        }).addTo(map);

        L.timeDimension.velocityLayer({
            baseURL: config.S3_BASE_URL,
            velocityLayerOptions: {
                velocityScale: 0.01,
                colorScale: ['#888'],
            }
        }).addTo(map);

        L.control.legend({
            serverUrl: config.SERVER_URL,
            layer: 'tmp'
        }).addTo(map);

        var layersControl = L.control.layers({
            'tmp': tmpLayer,
            'prate': prateLayer,
        }, []);
        layersControl.addTo(map);
    });
