import './App.css'
import 'leaflet/dist/leaflet.css';

import { useRef } from 'react';
import L, { Control } from 'leaflet';
import { LayersControl, MapContainer, TileLayer } from 'react-leaflet';

import VectorLayer from './VectorLayer';
import wind from './assets/wind-global.json';

function App() {
  const center: L.LatLngTuple = [47, -95];
  const layersControlRef = useRef<Control.Layers>(null);

  return (
    <MapContainer
      style={{ height: '100vh', width: '100wh' }}
      center={center}
      zoom={7}
      minZoom={5}
      maxZoom={11}
    >
      <TileLayer
        url="https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.jpg"
        attribution='&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        minZoom={0}
        maxZoom={20}
      />

      <LayersControl ref={layersControlRef} >

        <LayersControl.Overlay name='Temperature' checked>
          <TileLayer
            url='./src/assets/tiles/{z}/{x}/{y}.png'
            tms={true}
            opacity={0.4}
          />
        </LayersControl.Overlay>

        <LayersControl.Overlay name='Velocity' checked>
          <VectorLayer data={wind} />
        </LayersControl.Overlay>

      </LayersControl>
    </MapContainer> 
  )
}

export default App
