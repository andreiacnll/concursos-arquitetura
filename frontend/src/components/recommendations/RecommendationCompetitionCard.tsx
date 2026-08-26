"use client";

import { ExternalLink, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CompetitionCardBase } from "@/components/CompetitionCard";
import type { Concurso } from "@/components/competition-types";
import AnalysisConfirmationModal from "@/components/analises/AnalysisConfirmationModal";
import {
  analysisStatusLabel,
  type AnalysisJobState,
} from "@/lib/analysis-jobs";
import type { RecommendationCard as RecommendationCardType } from "./recommendation-types";

function translateKey(key: string): string {
  const known: Record<string, string> = {
    "competition.competences": "Competências por validar",
    "competition.preferences.typologies": "Tipologia não confirmada",
    "competition.project_experience.typologies": "Experiência semelhante em falta",
    "competition.location": "Localização por validar",
  };

  if (known[key]) return known[key];

  const lastPart = key.split(".").pop() ?? key;
  return lastPart
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function recommendationToConcurso(recommendation: RecommendationCardType): Concurso {
  return {
    id: recommendation.competition_id,
    titulo: recommendation.title,
    entidade: recommendation.entity || "Entidade não indicada",
    link: recommendation.link || `/concursos/${recommendation.competition_id}`,
    data: recommendation.published_at || "",
    relevante: 1,
    data_limite: recommendation.deadline || null,
    data_fim_calculada: recommendation.deadline || undefined,
    preco_base: recommendation.base_price || null,
    estado: "aberto",
    distrito: recommendation.location || null,
    municipio: recommendation.location || null,
    tipo_procedimento: recommendation.procedure_type || null,
    criterio_tipo: recommendation.award_criteria_type || null,
    criterio_resumo: recommendation.award_criteria_summary || null,
  };
}

function shortList<T>(items: T[], max: number): T[] {
  return items.slice(0, max).filter(Boolean);
}

function cleanSummary(summary: string, title: string): string {
  const trimmed = summary.trim();
  if (trimmed.startsWith(title)) {
    const rest = trimmed.slice(title.length).replace(/^[\s,.:;!?-]+/, "");
    if (rest.length > 10) return rest;
  }
  return trimmed;
}

function scoreLabel(score: number): string {
  if (score >= 80) return "Alta";
  if (score >= 60) return "Boa";
  if (score >= 40) return "Moderada";
  if (score >= 20) return "Baixa";
  return "Muito baixa";
}

export default function RecommendationCompetitionCard({
  recommendation,
  index,
  isFavorite,
  onToggleFavorite,
  analysisState,
  onCreateAnalysis,
}: {
  recommendation: RecommendationCardType;
  index: number;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  analysisState?: AnalysisJobState | null;
  onCreateAnalysis?: () => Promise<void>;
}) {
  const [showConfirmacao, setShowConfirmacao] = useState(false);
  const concurso = recommendationToConcurso(recommendation);
  const score = recommendation.compatibility_score;
  const hasScore = typeof score === "number";
  const strengths = shortList(recommendation.strengths, 3);
  const missing = recommendation.missing_information;
  const totalAttention = recommendation.attention_points.length + missing.length;
  const visibleAttention = shortList(
    [...recommendation.attention_points, ...missing.map(translateKey)],
    2,
  );
  const overflowCount = totalAttention - visibleAttention.length;
  const completed =
    analysisState?.status === "completed" || analysisState?.status === "partial";
  const failed =
    analysisState?.status === "failed" ||
    analysisState?.status === "interrupted" ||
    analysisState?.status === "cancelled";
  const processing =
    analysisState?.status === "queued" || analysisState?.status === "processing";

  return (
    <>
    <CompetitionCardBase
      concurso={concurso}
      index={index}
      isFavorite={isFavorite}
      onToggleFavorite={onToggleFavorite}
      showFavoriteButton
      className="recommendation-competition-card"
      badge={
        <span className="recommendation-competition-badge">
          Recomendado
        </span>
      }
      actions={
        <>
          <a
            href={concurso.link}
            className="card-link card-link-basegov"
            target={recommendation.link ? "_blank" : undefined}
            rel={recommendation.link ? "noreferrer" : undefined}
          >
            Ver concurso Base.gov
            <ExternalLink size={13} />
          </a>
          {completed ? (
            <Link
              href={`/analise/${recommendation.competition_id}`}
              className="card-link card-link-analise"
              style={{ background: "#111", color: "white", border: "none" }}
            >
              <Sparkles size={14} />
              Ver análise AI
            </Link>
          ) : processing ? (
            <button
              type="button"
              disabled
              className="card-link card-link-analise"
              style={{ background: "#111", color: "white", border: "none", cursor: "not-allowed", opacity: 0.82 }}
            >
              {analysisStatusLabel(analysisState)}
            </button>
          ) : failed ? (
            <button
              type="button"
              className="card-link card-link-analise"
              style={{ background: "#fff4f2", color: "#9f1c12", border: "1px solid #f2b8b5", cursor: "pointer" }}
              onClick={() => setShowConfirmacao(true)}
            >
              Tentar novamente
            </button>
          ) : (
            <button
              type="button"
              className="card-link card-link-analise"
              style={{ background: "#f0f4ea", color: "#607b43", border: "1px solid #607b43", cursor: "pointer" }}
              onClick={() => setShowConfirmacao(true)}
            >
              <Sparkles size={14} />
              Criar análise AI
            </button>
          )}
        </>
      }
    >
      {hasScore && (
        <div className="recommendation-score-block">
          <span className="recommendation-score-label">
            Score de compatibilidade
          </span>
          <div className="recommendation-score-value">
            <strong>{score}</strong>
            <span>/ 100</span>
          </div>
          <span className="recommendation-score-level">
            {scoreLabel(score)}
          </span>
        </div>
      )}

      <p className="recommendation-summary-compact">
        {cleanSummary(recommendation.summary, recommendation.title)}
      </p>

      {strengths.length > 0 && (
        <div className="recommendation-reasons">
          <span className="recommendation-reasons-label">Porque foi recomendado</span>
          <ul className="recommendation-reasons-list">
            {strengths.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {visibleAttention.length > 0 && (
        <div className="recommendation-attention">
          {visibleAttention.map((point, i) => (
            <span key={i} className="recommendation-attention-chip">
              {translateKey(point)}
            </span>
          ))}
          {overflowCount > 0 && (
            <span className="recommendation-attention-overflow">
              +{overflowCount}
            </span>
          )}
        </div>
      )}
    </CompetitionCardBase>
    <AnalysisConfirmationModal
      open={showConfirmacao}
      titulo={recommendation.title}
      entidade={recommendation.entity || ""}
      localizacao={recommendation.location || undefined}
      onClose={() => setShowConfirmacao(false)}
      onConfirm={async () => {
        if (!onCreateAnalysis) {
          throw new Error("Não foi possível iniciar a análise.");
        }
        await onCreateAnalysis();
        setShowConfirmacao(false);
      }}
    />
    </>
  );
}
