"use client";

import { useState } from "react";
import {
  Bookmark,
  CalendarDays,
  ExternalLink,
  MapPin,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { Concurso } from "./competition-types";
import { useAuth } from "@/context/AuthContext";
import AnalysisConfirmationModal from "./analises/AnalysisConfirmationModal";

function formatDataEntrega(valor?: string | null) {
  if (!valor) return "Sem data";

  const match = valor.match(
    /^(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2}))?/
  );

  if (!match) return valor;

  const [, dia, mes, ano, hora, minuto] = match;

  return `${dia}/${mes}/${ano}${
    hora && minuto ? ` ${hora}:${minuto}` : ""
  }`;
}


function diasRestantes(valor?: string | null) {
  if (!valor) return null;

  let entrega: Date;

  // formato API: YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}/.test(valor)) {
    const [ano, mes, dia] = valor.split("-").map(Number);

    entrega = new Date(
      ano,
      mes - 1,
      dia,
      23,
      59,
    );
  }

  // formato antigo: DD-MM-YYYY
  else {
    const match = valor.match(
      /^(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2}))?/
    );

    if (!match) return null;

    const [, dia, mes, ano, hora = "23", minuto = "59"] = match;

    entrega = new Date(
      Number(ano),
      Number(mes) - 1,
      Number(dia),
      Number(hora),
      Number(minuto),
    );
  }

  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const diferenca = entrega.getTime() - hoje.getTime();

  return Math.ceil(
    diferenca / (1000 * 60 * 60 * 24)
  );
}

const categoryImages = {
  "Saúde": [
    "/categories/saude.svg",
  ],

  "Habitação": [
    "/categories/habitacao.svg",
  ],

  "Escolas": [
    "/categories/escolas.svg",
  ],

  "Paisagismo": [
    "/categories/paisagismo.svg",
  ],

  "Espaço público": [
    "/categories/espaco-publico.svg",
  ],

  "Património": [
    "/categories/patrimonio.svg",
  ],

  "Arquitetura": [
    "/categories/arquitetura.svg",
  ],
};

function formatDate(value: string | null) {
  if (!value) return "Sem data";

  const partes = value.split("-");

  if (partes.length === 3) {
    return `${partes[2]}/${partes[1]}/${partes[0]}`;
  }

  return value;
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
  temAnalise,
  analiseEstado,
  onCriarAnalise,
}: {
  concurso: Concurso;
  index: number;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  temAnalise?: boolean;
  analiseEstado?: string;
  onCriarAnalise?: () => Promise<void>;
}) {
  const [tituloExpandido, setTituloExpandido] = useState(false);
  const [showConfirmacao, setShowConfirmacao] = useState(false);
  const { user } = useAuth();
  const tituloLongo = concurso.titulo.length > 75;

  const category = concurso.categoria || getCategory(concurso.titulo);

  const images =
    categoryImages[category as keyof typeof categoryImages] ??
    categoryImages["Arquitetura"];

  const image = images[index % images.length];

  const freshness = getFreshness(concurso.data);
  const location =
    concurso.municipio || concurso.distrito || concurso.entidade || "Portugal";

  function handleCriarAnalise() {
    setShowConfirmacao(true);
  }

  return (
    <article className="competition-card">
      <div className="card-image">

        <img
          src={image}
          alt={category}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
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

          {/* Bookmark apenas para utilizadores autenticados */}
          {user && (
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
          )}
        </div>

        <div className="card-meta">
          <span>
            <MapPin size={15} />
            {location}
          </span>
          <span>
            <CalendarDays size={15} />
            Publicado {formatDate(concurso.data)}
          </span>

          <span>
            📅 Entrega {formatDataEntrega(
              concurso.data_fim_calculada
            )}
          </span>

          {diasRestantes(concurso.data_fim_calculada) !== null && (
            <span>
              ⏳ {
                diasRestantes(concurso.data_fim_calculada)! > 0
                  ? `Faltam ${diasRestantes(concurso.data_fim_calculada)} dias`
                  : "Prazo terminado"
              }
            </span>
          )}
        </div>

        {concurso.criterio_tipo && (
          <div className="award-criteria">
            <span className="award-label">
              Critério de adjudicação
            </span>

            <strong>
              {concurso.criterio_tipo}
            </strong>

            <p>
              {concurso.criterio_resumo}
            </p>
          </div>
        )}

        <div className="procedure-info">
          <div className="procedure-type">
            {(concurso.tipo_procedimento || "Concurso público")
              .split(",")
              .map((item, i) => (
                <span key={i}>{item.trim()}</span>
              ))}
          </div>

          <strong className="price">
            {concurso.preco_base || "Valor não indicado"}
          </strong>
        </div>

        {/* Grupo de botões: Base.gov sempre visível + Análise AI (se autenticado) */}
        <div className="card-actions">
          {/* Link Base.gov - SEMPRE visível para todos os utilizadores */}
          <a
            className="card-link card-link-basegov"
            href={concurso.link}
            target="_blank"
            rel="noreferrer"
            aria-label={`Abrir concurso na Base.gov: ${concurso.titulo}`}
          >
            Ver concurso Base.gov
            <ExternalLink size={15} />
          </a>

          {/* Botão de análise AI - apenas para utilizadores autenticados */}
          {user && (
            temAnalise && analiseEstado === "concluida" ? (
              <Link
                href={`/analise/${concurso.id}`}
                className="card-link card-link-analise"
                style={{ background: "#111", color: "white", border: "none" }}
              >
                ✓ Ver análise AI
              </Link>
            ) : temAnalise ? (
              <Link
                href="/analises"
                className="card-link card-link-analise"
                style={{ background: "#111", color: "white", border: "none" }}
              >
                {analiseEstado === "aguarda" ? "⏳ Em fila" : "⚙ Em processamento"}
              </Link>
            ) : (
              <button
                type="button"
                className="card-link card-link-analise"
                style={{ background: "#f0f4ea", color: "#607b43", border: "1px solid #607b43", cursor: "pointer" }}
                onClick={handleCriarAnalise}
              >
                <Sparkles size={14} /> ✨ Criar análise AI
              </button>
            )
          )}
        </div>
      </div>

      <AnalysisConfirmationModal
        open={showConfirmacao}
        titulo={concurso.titulo}
        entidade={concurso.entidade}
        localizacao={concurso.municipio || concurso.distrito}
        onClose={() => setShowConfirmacao(false)}
        onConfirm={async () => {
          if (!onCriarAnalise) {
            throw new Error("Não foi possível iniciar a análise.");
          }
          await onCriarAnalise();
        }}
      />
    </article>
  );
}
