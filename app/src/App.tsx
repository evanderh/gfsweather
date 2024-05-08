import './App.css'

import { Viewer, Entity, PointGraphics } from "resium";
import { Cartesian3 } from "cesium";

const position = Cartesian3.fromDegrees(-74.0707383, 40.7117244, 100);

function App() {
  return (
    <Viewer
      full
    >
      <Entity position={position} name="Tokyo" description="Hello, world.">
        <PointGraphics pixelSize={10} />
      </Entity>
    </Viewer>
  )
}

export default App
