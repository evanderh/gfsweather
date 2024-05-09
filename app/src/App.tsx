import './App.css'
import { MapContainer, TileLayer, WMSTileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css';
// import surface from './assets/surface.json';

function App() {
  return (
    <MapContainer
      style={{ height: '100vh', width: '100wh' }}
      center={[38, -95]}
      zoom={5}
      minZoom={4}
      maxZoom={8}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        // terrain
        url='http://{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}'
        // satellite
        // url='http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        subdomains={['mt0','mt1','mt2','mt3']}
        // url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <TileLayer
        url='./src/assets/tiles/{z}/{x}/{y}.png'
        tms={true}
        opacity={0.7}
        minZoom={4}
        maxZoom={8}
      />

      {/* <WMSTileLayer
        url='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi'
        layers='nexrad-n0q-900913'
        format='image/png'
        transparent={true}
      /> */}
    </MapContainer> 
  )
}

export default App
