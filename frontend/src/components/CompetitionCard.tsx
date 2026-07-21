"use client";

import Image from "next/image";
import { useState } from "react";
import {
  Bookmark,
  CalendarDays,
  ExternalLink,
  MapPin,
} from "lucide-react";
import type { Concurso } from "./competition-types";

const categoryImages = {
  "Saúde": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Habitação": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Escolas": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Paisagismo": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Espaço público": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Património": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],

  "Arquitetura": [
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
    "/categories/architecture-1.svg",
  ],
};

function formatDate(value: string | null) {
  if (!value) return "Sem prazo indicado";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("pt-PT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function getCategory(title: string) {
  const text = title.toLowerCase();

  if (text.includes("escola") || text.includes("educa")) return "Escolas";
  if (text.includes("habita") || text.includes("resid")) return "Habitação";
  if (text.includes("jardim") || text.includes("paisag")) return "Paisagismo";
  if (text.includes("praça") || text.includes("largo") || text.includes("rua"))
    return "Espaço público";
  if (text.includes("saúde") || text.includes("hospital")) return "Saúde";
  if (text.includes("patrim") || text.includes("museu")) return "Património";

  return "Arquitetura";
}

function getFreshness(dateValue: string) {
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return null;

  const now = new Date();
  const diff = Math.floor(
    (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diff <= 0) return "Hoje";
  if (diff === 1) return "Ontem";
  if (diff <= 7) return `${diff} dias`;
  return null;
}

export default function CompetitionCard({
  concurso,
  index,
  isFavorite,
  onToggleFavorite,
}: {
  concurso: Concurso;
  index: number;
  isFavorite: boolean;
  onToggleFavorite: () => void;
}) {
  const [tituloExpandido, setTituloExpandido] = useState(false);
  const tituloLongo = concurso.titulo.length > 75;

  const category = concurso.categoria || getCategory(concurso.titulo);

  const images =
    categoryImages[category as keyof typeof categoryImages] ??
    categoryImages["Arquitetura"];

  const image = images[index % images.length];

  const freshness = getFreshness(concurso.data);
  const location =
    concurso.municipio || concurso.distrito || concurso.entidade || "Portugal";

  return (
    <article className="competition-card">
      <div className="card-image">

        <Image
          src={image}
          alt={category}
          fill
          priority={index < 6}
          sizes="(max-width:768px) 100vw, 33vw"
          style={{
            objectFit: "cover",
          }}
        />

        {freshness && (
          <span className="freshness-badge">
            {freshness}
          </span>
        )}

      </div>

      <div className="competition-card-body">
        <div className="card-heading-row">
          <div>
            <p className="category-label">{category}</p>

            <h3
              className={`competition-title ${
                tituloExpandido ? "is-expanded" : ""
              }`}
            >
              {concurso.titulo}
            </h3>

            {tituloLongo && (
              <button
                type="button"
                className="title-expand-button"
                aria-expanded={tituloExpandido}
                onClick={() => setTituloExpandido((valor) => !valor)}
              >
                {tituloExpandido ? "Ver menos −" : "Ver mais +"}
              </button>
            )}
          </div>

          <button
            type="button"
            className={`bookmark-button ${isFavorite ? "is-favorite" : ""}`}
            aria-label={
              isFavorite ? "Remover dos favoritos" : "Guardar nos favoritos"
            }
            aria-pressed={isFavorite}
            title={isFavorite ? "Remover dos favoritos" : "Guardar nos favoritos"}
            onClick={onToggleFavorite}
          >
            <Bookmark
              size={19}
              strokeWidth={1.65}
              fill={isFavorite ? "currentColor" : "none"}
            />
          </button>
        </div>

        <div className="card-meta">
          <span>
            <MapPin size={15} />
            {location}
          </span>
          <span>
            <CalendarDays size={15} />
            {formatDate(concurso.data_limite)}
          </span>
        </div>

        <div className="card-footer">
          <span>{concurso.tipo_procedimento || "Concurso público"}</span>
          <strong>{concurso.preco_base || "Valor não indicado"}</strong>
        </div>

        <a
          className="card-link"
          href={concurso.link}
          target="_blank"
          rel="noreferrer"
          aria-label={`Abrir ${concurso.titulo}`}
        >
          Ver concurso
          <ExternalLink size={15} />
        </a>
      </div>
    </article>
  );
}
