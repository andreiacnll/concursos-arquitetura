"use client";

import { Bookmark, ChevronRight, Lightbulb, AlertTriangle, HelpCircle, Sparkles, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { RecommendationCard as RecommendationCardType } from "./recommendation-types";

export default function RecommendationCard({
  recommendation,
  isFavorite,
  onToggleFavorite,
}: {
  recommendation: RecommendationCardType;
  isFavorite: boolean;
  onToggleFavorite: () => void;
}) {
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  const summaryLong = recommendation.summary.length > 160;

  return (
    <article className="recommendation-card">
      {/* Header */}
      <div className="rec-card-header">
        <div className="rec-card-title-row">
          <h3 className="rec-card-title">{recommendation.title}</h3>
          <button
            type="button"
            className={`rec-bookmark-button ${isFavorite ? "is-favorite" : ""}`}
            aria-label={isFavorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}
            aria-pressed={isFavorite}
            title={isFavorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onToggleFavorite();
            }}
          >
            <Bookmark
              size={18}
              strokeWidth={1.65}
              fill={isFavorite ? "currentColor" : "none"}
            />
          </button>
        </div>

        {/* Summary */}
        <p className={`rec-card-summary ${summaryExpanded ? "is-expanded" : ""}`}>
          {recommendation.summary}
        </p>
        {summaryLong && (
          <button
            type="button"
            className="rec-expand-button"
            aria-expanded={summaryExpanded}
            onClick={() => setSummaryExpanded((v) => !v)}
          >
            {summaryExpanded ? "Ver menos −" : "Ver mais +"}
          </button>
        )}
      </div>

      {/* Body */}
      <div className="rec-card-body">
        {/* Strengths */}
        {recommendation.strengths.length > 0 && (
          <div className="rec-tag-group">
            <span className="rec-tag-label">
              <Lightbulb size={14} />
              Pontos fortes
            </span>
            <div className="rec-tags">
              {recommendation.strengths.map((strength, i) => (
                <span key={i} className="rec-tag rec-tag-strength">
                  {strength}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Attention Points */}
        {recommendation.attention_points.length > 0 && (
          <div className="rec-tag-group">
            <span className="rec-tag-label">
              <AlertTriangle size={14} />
              Pontos de atenção
            </span>
            <div className="rec-tags">
              {recommendation.attention_points.map((point, i) => (
                <span key={i} className="rec-tag rec-tag-attention">
                  {point}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Missing Information */}
        {recommendation.missing_information.length > 0 && (
          <div className="rec-tag-group">
            <span className="rec-tag-label">
              <HelpCircle size={14} />
              Informação em falta
            </span>
            <div className="rec-tags">
              {recommendation.missing_information.map((info, i) => (
                <span key={i} className="rec-tag rec-tag-missing">
                  {info}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="rec-card-footer">
        <Link
          href={`/analise/${recommendation.competition_id}`}
          className="rec-action-link"
        >
          <Sparkles size={14} />
          {recommendation.action_label}
          <ChevronRight size={14} />
        </Link>
        <a
          href={`/concursos/${recommendation.competition_id}`}
          className="rec-detail-link"
        >
          Ver concurso
          <ExternalLink size={13} />
        </a>
      </div>
    </article>
  );
}