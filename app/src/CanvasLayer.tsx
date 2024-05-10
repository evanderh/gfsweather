import L from "leaflet";
import {createLayerComponent, LayerProps } from "@react-leaflet/core";
import { ReactNode } from "react";

function draw(tileSize: L.Point) {
  var canvas = document.createElement("canvas");
  canvas.width = tileSize.y;
  canvas.height = tileSize.x;
  var ctx = canvas.getContext("2d");
  if (!ctx) return '';
    
  var imageData = ctx.getImageData(0, 0, tileSize.x, tileSize.y);

  // for now just fill image with random data
  for (let i = 0; i < imageData.data.length; i++) {
    imageData.data[i] = Math.random() * 255
  }
  
  ctx.putImageData(imageData, 0, 0);

  return canvas.toDataURL();
}

interface CanvasLayer extends LayerProps {
  children?: ReactNode
}

class CanvasTile extends L.TileLayer {
  getTileUrl(coords: L.Coords) {
    // Convert pixel coordinates to latitude and longitude
    let tileSize = this.getTileSize();
    var nwPoint = L.point(tileSize.x * coords.x, tileSize.y * coords.y);
    var sePoint = nwPoint.add(L.point(tileSize.x, tileSize.y));
    var nwLatLng = this._map.unproject(nwPoint, coords.z);
    var seLatLng = this._map.unproject(sePoint, coords.z);
    console.log(nwLatLng, seLatLng);

    return draw(tileSize);
  }

  setUserId(userId: string) {
    console.log(userId)
  }
}

const createTemperatureLayer = (props: CanvasLayer, context: any) => {
  const instance = new CanvasTile("placeholder", {...props});
  return {instance, context};
}

const updateTemperatureLayer = (instance: CanvasTile, props: CanvasLayer, prevProps: CanvasLayer) => {
  if (prevProps !== props) {
    console.log(instance)
  }
}

const CanvasLayer = createLayerComponent(createTemperatureLayer, updateTemperatureLayer);
export default CanvasLayer;
