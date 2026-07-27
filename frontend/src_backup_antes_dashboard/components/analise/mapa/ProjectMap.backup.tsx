"use client";

import Map, { Marker } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";


type Props = {
  latitude: number;
  longitude: number;
};


export default function ProjectMap({
  latitude,
  longitude,
}: Props) {

  return (

    <div className="project-map">

      <Map

        mapboxAccessToken={
          process.env.NEXT_PUBLIC_MAPBOX_TOKEN
        }

        initialViewState={{
          latitude,
          longitude,
          zoom: 15,
        }}

        mapStyle="mapbox://styles/mapbox/light-v11"

        attributionControl={false}

        interactive={false}

      >

        <Marker
          latitude={latitude}
          longitude={longitude}
        />

      </Map>

    </div>

  );
}
