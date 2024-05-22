import './style.css'
import 'leaflet/dist/leaflet.css';
import "leaflet-velocity/dist/leaflet-velocity.css";

import L from 'leaflet';
import 'leaflet-velocity/dist/leaflet-velocity.js';
import wind from './assets/wind.json'

var map = L.map('map').setView([39, -98], 4);

L.tileLayer('http://localhost:8000/tiles/{z}/{x}/{y}.png').addTo(map);
L.tileLayer('http://localhost:8080/styles/osm-bright/256/{z}/{x}/{y}.png').addTo(map);
L.velocityLayer({
    displayValues: false,
    velocityScale: 0.01,
    opacity: 0.8,
    colorScale: ['#666'],
    data: wind,
}).addTo(map);
