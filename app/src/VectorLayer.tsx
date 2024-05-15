import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet-velocity/dist/leaflet-velocity.css";
import 'leaflet-velocity/dist/leaflet-velocity.js';
import { useLeafletContext } from "@react-leaflet/core";

interface Props {
  data: any,
}
const VectorLayer = ({ data }: Props) => {
  const context = useLeafletContext();
  const layerRef = useRef<any>();

  useEffect(() => {
    var container = context.layerContainer || context.map;

    if (!layerRef.current) {
      // @ts-ignore
      layerRef.current = L.velocityLayer({
        displayValues: true,
        displayOptions: {
          velocityType: "Global Wind",
          position: "bottomleft",
          emptyString: "No water data"
        },
        velocityScale: 0.01,
        opacity: 0.8,
        colorScale: ['#888'],
        data,
      })
    }

    container.addLayer(layerRef.current);

    return () => {
      container.removeLayer(layerRef.current);
    }
  }, [data]);

  return null;
}

export default VectorLayer;
