import './style.css'
import 'leaflet/dist/leaflet.css';
import 'leaflet-velocity/dist/leaflet-velocity.css';
import 'leaflet-timedimension/dist/leaflet.timedimension.control.css';

import L from 'leaflet';
import 'leaflet-velocity/dist/leaflet-velocity.js';
import 'leaflet-timedimension/dist/leaflet.timedimension.src.js';
import './TimeLayer.js';
import './TimeVelocityLayer.js';
import './Legend.js';

import { config } from './config.js';
import { layersConfig } from './LayersConfig.js';

fetch(`${config.API_URL}/forecast_cycle`)
    .then(response => response.json())
    .then(data => {
        let { startDatetime, hourLimit } = data;
        let start = (new Date(startDatetime+'Z')).toISOString()
                                                 .substring(0, 13);

        let map = L.map('map', {
            center: [20, -10],
            zoom: 3,
            minZoom: 3,
            maxZoom: 6,
            zoomSnap: 0.5,
            zoomDelta: 1,
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


        L.tileLayer(`${config.TILES_URL}/osm-bright/256/{z}/{x}/{y}.png`, {
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            zIndex: 19,
        }).addTo(map);

        L.timeDimension.velocityLayer({
            baseURL: `${config.LAYERS_URL}/${start}`,
            velocityLayerOptions: {
                velocityScale: 0.01,
                colorScale: ['#888'],
            }
        }).addTo(map);

        var layers = {}
        Object.entries(layersConfig).forEach(([name, layer]) => {
            layers[name] = L.timeDimension.timeLayer(
                L.tileLayer(`${config.LAYERS_URL}/${start}/{d}/${layer}/{z}/{x}/{y}.png`, {
                    tms: true,
                })
            );
        })

        var defaultLayer = 'Temperature';

        layers[defaultLayer].addTo(map)

        L.control.legend({
            baseUrl: config.LAYERS_URL,
            defaultLayer,
        }).addTo(map);

        var layersControl = L.control.layers(layers, []);
        layersControl.addTo(map);
    });
