"use client";

import { type ReactNode, useState } from "react";
import {
  Bookmark,
  CalendarDays,
  ExternalLink,
  MapPin,
  Sparkles,
} from "lucide-react";
import type { Concurso } from "./competition-types";
import { useAuth } from "@/context/AuthContext";
import AnalysisConfirmationModal from "./analises/AnalysisConfirmationModal";
import { analysisStatusLabel } from "@/lib/analysis-jobs";
import { getCompetitionPublication } from "@/lib/competition-dates";
import { getCompetitionAwardCriteria } from "@/lib/competition-award-criteria";

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

  if (/^\d{4}-\d{2}-\d{2}/.test(valor)) {
    const [ano, mes, dia] = valor.split("-").map(Number);

    entrega = new Date(
      ano,
      mes - 1,
      dia,
      23,
      59,
    );
  } else {
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
  Saude: [
    "/categories/saude.svg",
  ],

  Habitacao: [
    "/categories/habitacao.svg",
  ],

  Escolas: [
    "/categories/escolas.svg",
  ],

  Paisagismo: [
    "/categories/paisagismo.svg",
  ],

  "Espaco publico": [
    "/categories/espaco-publico.svg",
  ],

  Patrimonio: [
    "/categories/patrimonio.svg",
  ],

  Arquitetura: [
    "/categories/arquitetura.svg",
  ],
};

function getCategory(title: string) {
  const text = title.toLowerCase();

  if (text.includes("escola") || text.includes("educa")) return "Escolas";
  if (text.includes("habita") || text.includes("resid")) return "Habitacao";
  if (text.includes("jardim") || text.includes("paisag")) return "Paisagismo";
  if (text.includes("praca") || text.includes("largo") || text.includes("rua"))
    return "Espaco publico";
  if (text.includes("saude") || text.includes("hospital")) return "Saude";
  if (text.includes("patrim") || text.includes("museu")) return "Patrimonio";

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

function sourceAction(concurso: Concurso) {
  const source = (concurso.fonte || "").toLowerCase();
  const link = (concurso.link || "").toLowerCase();

  if (
    source === "lisboa_sru" ||
    link.includes("lisboasru.pt")
  ) {
    return {
      label: "Ver concurso Lisboa SRU",
      aria: `Abrir concurso na Lisboa SRU: ${concurso.titulo}`,
    };
  }

  if (source === "oasrs_encomenda") {
    return {
      label: "Ver concurso OA-SRS",
      aria: `Abrir concurso na Plataforma Encomenda OA-SRS: ${concurso.titulo}`,
    };
  }

  if (source === "ordem_arquitectos") {
    return {
      label: "Ver concurso na Ordem",
      aria: `Abrir concurso na Ordem dos Arquitectos: ${concurso.titulo}`,
    };
  }

  if (source === "espaco") {
    return {
      label: "Ver concurso",
      aria: `Abrir concurso na fonte original: ${concurso.titulo}`,
    };
  }

  if (source === "base_gov" || link.includes("base.gov.pt")) {
    return {
      label: "Ver concurso Base.gov",
      aria: `Abrir concurso na Base.gov: ${concurso.titulo}`,
    };
  }

  return {
    label: "Ver anúncio oficial",
    aria: `Abrir concurso na fonte oficial: ${concurso.titulo}`,
  };
}


export function CompetitionCardBase({
  concurso,
  index,
  isFavorite,
  onToggleFavorite,
  showFavoriteButton,
  badge,
  children,
  actions,
  className = "",
}: {
  concurso: Concurso;
  index: number;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  showFavoriteButton: boolean;
  badge?: ReactNode;
  children?: ReactNode;
  actions: ReactNode;
  className?: string;
}) {
  const [tituloExpandido, setTituloExpandido] = useState(false);
  const tituloLongo = concurso.titulo.length > 75;

  const category = concurso.categoria || getCategory(concurso.titulo);
  const images =
    categoryImages[category as keyof typeof categoryImages] ??
    categoryImages.Arquitetura;
  const image = images[index % images.length];
  const publication = getCompetitionPublication(concurso);
  const freshness = getFreshness(publication?.rawDate || "");
  const isSearchCard = className.split(/\s+/).includes("search-competition-card");
  const location =
    concurso.municipio || concurso.distrito || concurso.entidade || "Portugal";

  const submissionDeadline =
    concurso.data_entrega_propostas ||
    concurso.data_fim_calculada ||
    concurso.data_limite;
  const awardCriteria = getCompetitionAwardCriteria(concurso);

  return (
    <article className={`competition-card ${className}`.trim()} data-category={category}>
      <div className="card-image">
        <img
          src={image}
          alt={category}
          className="card-illustration"
        />

        {freshness && (
          <span className="freshness-badge">
            {freshness}
          </span>
        )}

        {badge}
      </div>

      <div className="competition-card-body">
        <div className="card-heading-row">
          <div>
            <p className="category-label">{category}</p>
            {concurso.has_updates ? (
              <span className="competition-update-badge" title={concurso.changed_fields || "Concurso atualizado"}>⚠ Atualizado</span>
            ) : null}

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
                {tituloExpandido ? "Ver menos -" : "Ver mais +"}
              </button>
            )}
          </div>

          {showFavoriteButton && (
            <button
              type="button"
              className={`bookmark-button ${isFavorite ? "is-favorite" : ""}`}
              aria-label={
                isFavorite ? "Remover dos favoritos" : "Guardar nos favoritos"
              }
              aria-pressed={isFavorite}
              title={isFavorite ? "Remover dos favoritos" : "Guardar nos favoritos"}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onToggleFavorite();
              }}
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
          {publication && (
            <span>
              <CalendarDays size={15} />
              {publication.label} {publication.date}
            </span>
          )}

          <span>
            Entrega {formatDataEntrega(submissionDeadline)}
          </span>

          {diasRestantes(submissionDeadline) !== null && (
            <span>
              {
                diasRestantes(submissionDeadline)! > 0
                  ? `Faltam ${diasRestantes(submissionDeadline)} dias`
                  : "Prazo terminado"
              }
            </span>
          )}
        </div>

        {awardCriteria && (
          <div className="award-criteria">
            <span className="award-label">
              Criterio de adjudicacao
            </span>

{awardCriteria.factors.length ? (
              <strong className="award-factor-list">
                {awardCriteria.factors.map((factor) => (
                  <span key={`${factor.name}-${factor.weight}`}>
                    {factor.name} · {factor.weight}%
                  </span>
                ))}
              </strong>
            ) : (
              <strong>{awardCriteria.primary}</strong>
            )}

            {awardCriteria.secondary && <p>{awardCriteria.secondary}</p>}
          </div>
        )}

        {isSearchCard ? (
          <div className="procedure-info">
            <div className="procedure-detail">
              <span className="card-info-label">Procedimento</span>
              <div className="procedure-type">
                {(concurso.tipo_procedimento || "Concurso publico")
                  .split(",")
                  .map((item, i) => (
                    <span key={i}>{item.trim()}</span>
                  ))}
              </div>
            </div>

            <div className="procedure-detail price-detail">
              <span className="card-info-label">Valor base</span>
              <strong className="price">
                {concurso.preco_base || "Valor nao indicado"}
              </strong>
            </div>
          </div>
        ) : (
          <div className="procedure-info">
            <div className="procedure-type">
              {(concurso.tipo_procedimento || "Concurso publico")
                .split(",")
                .map((item, i) => (
                  <span key={i}>{item.trim()}</span>
                ))}
            </div>

            <strong className="price">
              {concurso.preco_base || "Valor nao indicado"}
            </strong>
          </div>
        )}
        {children}

        <div className="card-actions">
          {actions}
        </div>
      </div>
    </article>
  );
}

export default function CompetitionCard({
  concurso,
  index,
  isFavorite,
  onToggleFavorite,
  temAnalise,
  analiseEstado,
  analiseStage,
  onCriarAnalise,
  badge,
  className = "",
}: {
  concurso: Concurso;
  index: number;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  temAnalise?: boolean;
  analiseEstado?: string;
  analiseStage?: string;
  onCriarAnalise?: () => Promise<void>;
  badge?: ReactNode;
  className?: string;
}) {
  const [showConfirmacao, setShowConfirmacao] = useState(false);
  const { user } = useAuth();
  const source = sourceAction(concurso);
  const hasOfficialLink = /^https?:\/\//i.test((concurso.link || "").trim());
  const analysisVersion =
    concurso.updatedAtAnalise ||
    concurso.analiseId ||
    "latest";
  const analysisHref =
    `/analise/${concurso.id}?v=${encodeURIComponent(String(analysisVersion))}`;

  function handleCriarAnalise() {
    setShowConfirmacao(true);
  }

  return (
    <>
      <CompetitionCardBase
        concurso={concurso}
        index={index}
        isFavorite={isFavorite}
        onToggleFavorite={onToggleFavorite}
        showFavoriteButton={Boolean(user)}
        badge={badge}
        className={className}
        actions={
          <>
            {hasOfficialLink ? (
              <a
                className="card-link card-link-basegov"
                href={concurso.link}
                target="_blank"
                rel="noreferrer"
                aria-label={source.aria}
              >
                {source.label}
                <ExternalLink size={15} />
              </a>
            ) : (
              <span className="card-link card-link-basegov card-link-unavailable">
                Sem link oficial
              </span>
            )}

            {user && (
              temAnalise && ["concluida", "completed", "partial"].includes(analiseEstado || "") ? (
                <a
                  href={analysisHref}
                  className="card-link card-link-analise"
                  style={{ background: "#111", color: "white", border: "none" }}
                >
                  Ver analise AI
                </a>
              ) : temAnalise && ["erro", "failed", "cancelada", "cancelled", "interrupted"].includes(analiseEstado || "") ? (
                <button
                  type="button"
                  className="card-link card-link-analise"
                  style={{ background: "#fff4f2", color: "#9f1c12", border: "1px solid #f2b8b5", cursor: "pointer" }}
                  onClick={() => setShowConfirmacao(true)}
                >
                  Tentar novamente
                </button>
              ) : temAnalise ? (
                <button
                  type="button"
                  disabled
                  className="card-link card-link-analise"
                  style={{ background: "#111", color: "white", border: "none", cursor: "not-allowed", opacity: 0.82 }}
                >
                  {analysisStatusLabel({
                    job_id: 0,
                    concurso_id: concurso.id,
                    status: analiseEstado === "aguarda" ? "queued" : "processing",
                    stage: analiseStage || analiseEstado,
                  })}
                </button>
              ) : (
                <button
                  type="button"
                  className="card-link card-link-analise"
                  style={{ background: "#f0f4ea", color: "#607b43", border: "1px solid #607b43", cursor: "pointer" }}
                  onClick={handleCriarAnalise}
                >
                  <Sparkles size={14} /> Criar analise AI
                </button>
              )
            )}
          </>
        }
      />

      <AnalysisConfirmationModal
        open={showConfirmacao}
        titulo={concurso.titulo}
        entidade={concurso.entidade}
        localizacao={concurso.municipio || concurso.distrito}
        onClose={() => setShowConfirmacao(false)}
        onConfirm={async () => {
          if (!onCriarAnalise) {
            throw new Error("Nao foi possivel iniciar a analise.");
          }
          await onCriarAnalise();
        }}
      />
    </>
  );
}
