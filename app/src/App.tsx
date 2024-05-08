import './App.css'
import { MapContainer, TileLayer, WMSTileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css';
// import surface from './assets/surface.json';

function App() {
  return (
    <MapContainer
      style={{ height: '100vh', width: '100wh' }}
      center={[38, -95]}
      zoom={5}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <WMSTileLayer
        url='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi'
        layers='nexrad-n0r-900913'
        format='image/png'
        transparent={true}
      />
    </MapContainer> 
  )
}

export default App
