"use client";

import { useEffect, useState } from "react";
import "./Timeline.css";
import { API_URL } from "@/lib/api";


type Evento = {
  tipo: string;
  titulo: string;
  data: string | null;
  origem: string | null;
};


type Props = {
  concursoId: string;
};


const fasesBase = [
  "Publicado",
  "Pedidos de esclarecimento",
  "Visita ao local",
  "Entrega de propostas",
  "Avaliação",
  "Adjudicação",
  "Contrato",
];


export default function Timeline({
  concursoId,
}: Props) {

  const [eventos, setEventos] =
    useState<Evento[]>([]);


  useEffect(() => {

    fetch(
      `${API_URL}/concursos/${concursoId}/timeline`
    )
      .then(
        resposta => resposta.json()
      )
      .then(
        dados => setEventos(dados)
      );

  }, [concursoId]);


  function encontrarEvento(nome:string) {

    return eventos.find(
      evento =>
        evento.titulo
          .toLowerCase()
          .includes(
            nome
              .toLowerCase()
              .split(" ")[0]
          )
    );

  }


  return (

    <section className="timeline-dashboard">

      <h2>
        Timeline do concurso
      </h2>


      <div className="timeline-wrapper">


        <div className="timeline-track">


          {fasesBase.map(
            (fase,index)=> {

              const evento =
                encontrarEvento(fase);


              const concluido =
                !!evento;


              return (

                <div
                  key={fase}
                  className="timeline-step"
                >

                  <div
                    className={
                      concluido
                      ? "timeline-circle active"
                      : "timeline-circle"
                    }
                  >

                    {concluido
                      ? "✓"
                      : ""
                    }

                  </div>


                  <div className="timeline-label">

                    <strong>
                      {fase}
                    </strong>

                    <span>
                      {evento?.data ?? "Por definir"}
                    </span>

                  </div>


                </div>

              );

            }
          )}

        </div>


      </div>


    </section>

  );

}
