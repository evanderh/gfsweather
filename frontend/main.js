import './style.css'
import 'mapbox-gl/dist/mapbox-gl.css';

import mapboxgl from 'mapbox-gl'; // or "const mapboxgl = require('mapbox-gl');"

mapboxgl.accessToken = 'pk.eyJ1IjoiZXZhbmRlcmgiLCJhIjoiY2x5bnM3bzduMDlzZTJrcHRncXI4MWNiYyJ9.5IREPfoU_ulCHL0Oxjxq1w';
const SERVER_URL = import.meta.env.VITE_SERVER_URL;
const TILES_URL = import.meta.env.VITE_TILES_URL;

const map = new mapboxgl.Map({
    container: 'map', // container ID
    center: [-74.5, 40], // starting position [lng, lat]. Note that lat must be set between -90 and 90
    zoom: 3,
    minZoom: 3,
    maxZoom: 6,
});

const hoursPerForecast = 3;

async function fetchData() {
    try {
        const response = await fetch(`${SERVER_URL}/api/forecast_cycle`)
        if (!response.ok) {
            throw new Error("Failed to fetch forecast cycle!")
        }
        const data = await response.json();
        return data;
    } catch(error) {
        console.error('Fetch error: ', error);
        return null;
    }
}

function render(startDatetime, numForecasts) {
    let hourLimit = (numForecasts - 1) * hoursPerForecast;
    let start = (new Date(startDatetime)).toISOString()
                                         .substring(0, 13);

    map.addSource('custom-tiles', {
        type: 'raster',
        tiles: [
            `${SERVER_URL}/layers/${start}/${start}/tmp/{z}/{x}/{y}.png`
        ],
        tileSize: 256,
        scheme: 'tms'
    });

    // Add a layer for your custom tile source
    map.addLayer({
        'id': 'custom-tiles-layer',
        'type': 'raster',
        'source': 'custom-tiles',
        'paint': {}
    });
}

let lastStartDatetime;
async function init() {
    const data = await fetchData();
    if (data) {
        let { startDatetime, numForecasts } = data;
        if (lastStartDatetime !== startDatetime) {
            render(startDatetime, numForecasts);
            lastStartDatetime = startDatetime;
        }
    }
}

map.on('load', () => {
    init();
});

// document.addEventListener('DOMContentLoaded', () => {
//     document.addEventListener('visibilitychange', () => {
//         if (document.visibilityState === 'visible') {
//             console.log('Reloading')
//             init();
//         }
//     });

//     init();
// });


// import 'leaflet/dist/leaflet.css';
// import 'leaflet-velocity/dist/leaflet-velocity.css';
// import 'leaflet-timedimension/dist/leaflet.timedimension.control.css';

// import L from 'leaflet';
// import 'leaflet-velocity/dist/leaflet-velocity.js';
// import 'leaflet-timedimension/dist/leaflet.timedimension.src.js';
// import './src/TimeLayer.js';
// import './src/TimeVelocityLayer.js';
// import './src/legend.js';
// import { layers } from './src/layers.js';



// let map;

// function render(startDatetime, numForecasts) {
//     let hourLimit = (numForecasts - 1) * hoursPerForecast;
//     let start = (new Date(startDatetime)).toISOString()
//                                              .substring(0, 13);

//     if (map) {
//         map.off();
//         map.remove()
//     }
    
//     map = L.map('map', {
//         center: [20, -10],
//         zoom: 3,
//         minZoom: 3,
//         maxZoom: 6,
//         zoomSnap: 0.5,
//         zoomDelta: 1,
//         maxBounds: [[-85, -720], [85, 720]],
//         timeDimension: true,
//         timeDimensionOptions: {
//             timeInterval: `${startDatetime}/PT${hourLimit}H`,
//             period: `PT${hoursPerForecast}H`,
//         },
//         timeDimensionControl: true,
//         timeDimensionControlOptions: {
//             playerOptions: {
//                 transitionTime: 2000,
//             },
//             timeZones: ["Local"],
//             playButton: true,
//             loopButton: true,
//             speedSlider: false,
//         },
//     });

//     L.tileLayer(`${TILES_URL}/styles/osm-bright/256/{z}/{x}/{y}.png`, {
//         attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
//         zIndex: 19,
//     }).addTo(map);

//     L.timeDimension.velocityLayer({
//         baseURL: `${SERVER_URL}/layers/${start}`,
//         velocityLayerOptions: {
//             velocityScale: 0.01,
//             colorScale: ['#888'],
//         }
//     }).addTo(map);

//     var tileLayers = {}
//     Object.entries(layers).forEach(([name, layer]) => {
//         tileLayers[name] = L.timeDimension.timeLayer(
//             L.tileLayer(`${SERVER_URL}/layers/${start}/{d}/${layer}/{z}/{x}/{y}.png`, {
//                 tms: true,
//             })
//         );
//     })

//     var defaultLayer = 'Temperature';

//     tileLayers[defaultLayer].addTo(map)

//     L.control.legend({
//         baseUrl: `${SERVER_URL}/layers`,
//         defaultLayer,
//     }).addTo(map);

//     var layersControl = L.control.layers(tileLayers, []);
//     layersControl.addTo(map);
// }



