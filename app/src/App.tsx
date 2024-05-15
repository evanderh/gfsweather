import './App.css'
import 'leaflet/dist/leaflet.css';

import L from 'leaflet';
import { LayersControl, MapContainer, TileLayer, WMSTileLayer } from 'react-leaflet';

import VectorLayer from './VectorLayer';
import wind from './assets/wind.json';

function App() {
  const center: L.LatLngTuple = [36, -119];

  return (
    <MapContainer
      style={{ height: '100vh', width: '100wh' }}
      center={center}
      zoom={6}
      minZoom={2}
      maxZoom={9}
    >
      <TileLayer
        url='http://localhost:8080/styles/osm-bright/256/{z}/{x}/{y}.png'
        zIndex={4}
        attribution=''
      />
     
      <LayersControl>

        <LayersControl.Overlay name='Temperature' checked>
          <TileLayer
            url='http://localhost:8000/tiles/{z}/{x}/{y}.png'
            opacity={0.8}
          />
        </LayersControl.Overlay>

        <LayersControl.Overlay name='Velocity' checked>
          <VectorLayer data={wind} />
        </LayersControl.Overlay>

        <LayersControl.Overlay name='Radar'>
          <WMSTileLayer
            url='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi'
            layers='nexrad-n0q-900913'
            format='image/png'
            transparent
            zIndex={3}
          />
        </LayersControl.Overlay>

      </LayersControl>
      

    </MapContainer> 
  )
}

export default App
