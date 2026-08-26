"use client";

import Map, { Marker } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";


type Props = {
  latitude:number;
  longitude:number;
};


export default function ProjectMap({
  latitude,
  longitude,
}:Props){


  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;


  const openStreetMapUrl =
    `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=16/${latitude}/${longitude}`;



  if(!token || token === "COLOCA_AQUI_O_TOKEN"){

    return (

      <a
        className="project-map-placeholder"
        href={openStreetMapUrl}
        target="_blank"
        rel="noopener noreferrer"
      >

        <div>
          📍
        </div>

        <span>
          Ver localização no mapa
        </span>

      </a>

    );

  }



  return (

    <div className="project-map">

      <Map

        mapboxAccessToken={token}

        initialViewState={{
          latitude,
          longitude,
          zoom:15,
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
