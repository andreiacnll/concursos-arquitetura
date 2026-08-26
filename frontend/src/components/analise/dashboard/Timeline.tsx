"use client";

import { useEffect, useMemo, useState } from "react";
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

function hasUsefulDate(evento: Evento) {
  return Boolean(evento.data && evento.data.trim());
}

export default function Timeline({ concursoId }: Props) {
  const [eventos, setEventos] = useState<Evento[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/concursos/${concursoId}/timeline`)
      .then((resposta) => resposta.json())
      .then((dados) => setEventos(Array.isArray(dados) ? dados : []))
      .catch(() => setEventos([]));
  }, [concursoId]);

  const usefulEvents = useMemo(
    () => eventos.filter((evento) => hasUsefulDate(evento) && Boolean(evento.titulo)),
    [eventos],
  );

  if (usefulEvents.length < 2) {
    return null;
  }

  return (
    <section className="timeline-dashboard">
      <h2>Timeline do concurso</h2>
      <div className="timeline-wrapper">
        <div className="timeline-track">
          {usefulEvents.map((evento, index) => (
            <div key={`${evento.titulo}-${index}`} className="timeline-step">
              <div className="timeline-circle active">✓</div>
              <div className="timeline-label">
                <strong>{evento.titulo}</strong>
                <span>{evento.data}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
