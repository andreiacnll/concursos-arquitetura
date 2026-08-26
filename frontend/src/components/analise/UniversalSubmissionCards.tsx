"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ClipboardCheck,
  FileCheck2,
  FileText,
} from "lucide-react";
import { buildUniversalSubmission } from "@/lib/analysis-universal";
import {
  dedupeDisplayItems,
  type AnalysisDisplayKind,
  formatAnalysisItemForDisplay,
} from "@/lib/analysis-display";

type AnyRecord = Record<string, any>;

type Props = {
  ficha: AnyRecord;
  procedureAnalysis: AnyRecord;
};

function renderRows(
  items: AnyRecord[],
  empty: string,
  limit = 6,
  kind: AnalysisDisplayKind = "generic",
) {
  return (
    <SubmissionRows
      items={items}
      empty={empty}
      limit={limit}
      kind={kind}
    />
  );
}

function SubmissionRows({
  items,
  empty,
  limit,
  kind,
}: {
  items: AnyRecord[];
  empty: string;
  limit: number;
  kind: AnalysisDisplayKind;
}) {
  const [expanded, setExpanded] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const displayItems = useMemo(() => dedupeDisplayItems(items), [items]);

  if (!displayItems.length) return <p className="dc-empty">{empty}</p>;

  const visible = expanded ? displayItems : displayItems.slice(0, limit);
  const displayRows = visible.map((item) => formatAnalysisItemForDisplay(item, kind));
  const sources = displayItems
    .map((item) => formatAnalysisItemForDisplay(item, kind))
    .filter((display) => display.hasMoreDetail);
  const remaining = Math.max(displayItems.length - limit, 0);

  return (
    <div className="analysis-display-list">
      <div className="analysis-items">
        {displayRows.map((display, index) => (
          <div className="analysis-display-item" key={`${display.label}-${index}`}>
            <div>
              <span className="analysis-display-label">{display.label}</span>
              <strong title={display.provenance}>{display.primaryValue}</strong>
            </div>
            {display.qualifiers.length ? (
              <div className="analysis-qualifiers">
                {display.qualifiers.map((qualifier) => (
                  <span key={qualifier}>{qualifier}</span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="analysis-actions">
        {sources.length ? (
          <button
            type="button"
            className="analysis-sources-button"
            onClick={() => setSourcesOpen(!sourcesOpen)}
            aria-expanded={sourcesOpen}
          >
            {sourcesOpen ? "Ocultar fontes" : `Fontes (${sources.length})`}
          </button>
        ) : null}

        {remaining > 0 ? (
          <button
            type="button"
            className="analysis-show-all"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
          >
            {expanded ? "Mostrar menos" : `Ver todos (${displayItems.length})`}
          </button>
        ) : null}
      </div>

      {sourcesOpen ? (
        <div className="analysis-source-list">
          {sources.map((display, index) => {
            const sourceLabel = [
              display.source.document,
              display.source.section,
              display.source.page ? `p. ${display.source.page}` : "",
            ]
              .filter(Boolean)
              .join(" · ");

            return (
              <div key={`${display.label}-source-${index}`} className="analysis-source-detail">
                <strong>{display.label}</strong>
                <small>{display.provenance}</small>
                {sourceLabel ? <small>Fonte: {sourceLabel}</small> : null}
                {display.source.excerpt ? <p>{display.source.excerpt}</p> : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <style jsx>{`
        .analysis-display-list {
          display: grid;
          gap: 12px;
        }

        :global(.procedure-summary) {
          display: flex;
          align-items: baseline;
          gap: 8px;
          margin: 10px 0 14px;
        }

        :global(.procedure-summary strong) {
          font-size: 24px;
          line-height: 1;
          font-weight: 700;
        }

        :global(.procedure-summary span) {
          color: #6a6e68;
          font-size: 11px;
          line-height: 1.35;
        }

        .analysis-items {
          display: grid;
          gap: 8px;
        }

        .analysis-display-item {
          display: grid;
          gap: 6px;
          padding: 10px 0;
          border-bottom: 1px solid rgba(20, 45, 35, 0.07);
        }

        .analysis-display-item:last-child {
          border-bottom: 0;
        }

        .analysis-display-item > div:first-child {
          display: grid;
          gap: 3px;
        }

        .analysis-display-label {
          color: #59615a;
          font-size: 12px;
          line-height: 1.35;
        }

        .analysis-display-item strong {
          color: #1f332a;
          font-size: 13px;
          line-height: 1.35;
          text-align: left;
          max-width: none;
        }

        .analysis-qualifiers {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
        }

        .analysis-qualifiers span {
          border-radius: 999px;
          background: #f1f4ec;
          color: #536943;
          font-size: 10px;
          line-height: 1;
          padding: 5px 7px;
        }

        .analysis-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .analysis-sources-button,
        .analysis-show-all {
          border: 0;
          background: transparent;
          color: #587436;
          cursor: pointer;
          font-size: 11px;
          font-weight: 700;
          text-decoration: underline;
          text-underline-offset: 2px;
        }

        .analysis-source-list {
          display: grid;
          gap: 8px;
        }

        .analysis-source-detail {
          display: grid;
          gap: 4px;
          padding: 8px 10px;
          border-radius: 10px;
          background: #f7f7f2;
          color: #62665f;
        }

        .analysis-source-detail strong {
          color: #314137;
          font-size: 11px;
        }

        .analysis-source-detail small {
          font-size: 10px;
          line-height: 1.35;
        }

        .analysis-source-detail p {
          margin: 0;
          font-size: 11px;
          line-height: 1.45;
        }
      `}</style>
    </div>
  );
}

function metric(count: number): string {
  return count > 0 ? String(count) : "0";
}

export default function UniversalSubmissionCards({
  ficha,
  procedureAnalysis,
}: Props) {
  const data = buildUniversalSubmission(ficha, procedureAnalysis);

  return (
    <>
      <article className="dc-card analysis-card-medium">
        <div className="dc-card-title">
          <ClipboardCheck size={18} />
          <h3>Documentos que instruem a proposta</h3>
        </div>
        <div className="procedure-summary">
          <strong>{metric(data.participantDocuments.length)}</strong>
          <span>
            {data.participantDocuments.length
              ? "documentos obrigatórios identificados"
              : "não identificado nas peças processadas"}
          </span>
        </div>
        {renderRows(
          data.participantDocuments,
          "Documentos obrigatórios ainda não identificados nas peças processadas.",
          6,
          "document",
        )}
      </article>

      <article className="dc-card analysis-card-wide">
        <div className="dc-card-title">
          <FileText size={18} />
          <h3>Conteúdo técnico da proposta</h3>
        </div>
        <div className="procedure-summary">
          <strong>{metric(data.proposalDocuments.length)}</strong>
          <span>
            {data.proposalDocuments.length
              ? "elementos técnicos identificados"
              : "não identificado nas peças processadas"}
          </span>
        </div>
        {renderRows(
          data.proposalDocuments,
          "Conteúdo técnico ainda não identificado nas peças processadas.",
          6,
          "technical",
        )}
      </article>

      <article className="dc-card analysis-card-medium">
        <div className="dc-card-title">
          <FileCheck2 size={18} />
          <h3>Formatos e submissão</h3>
        </div>
        <div className="procedure-summary">
          <strong>{metric(data.formatsAndLimits.length)}</strong>
          <span>
            {data.formatsAndLimits.length
              ? "regras identificadas"
              : "não identificado nas peças processadas"}
          </span>
        </div>
        {renderRows(
          data.formatsAndLimits,
          "Formatos e limites ainda não identificados nas peças processadas.",
          6,
          "format",
        )}
      </article>

      <article className="dc-card analysis-card-medium">
        <div className="dc-card-title">
          <AlertTriangle size={18} />
          <h3>Exclusões explícitas</h3>
        </div>
        <div className="procedure-summary">
          {data.criticalConditions.length ? (
            <strong>{metric(data.criticalConditions.length)}</strong>
          ) : null}
          <span>
            {data.criticalConditions.length
              ? "condições críticas identificadas"
              : "Nenhuma exclusão explícita identificada"}
          </span>
        </div>
        {renderRows(
          data.criticalConditions,
          "Nenhuma exclusão explícita identificada nas peças processadas.",
          5,
          "exclusion",
        )}
      </article>

      <style jsx>{`
        .analysis-card-wide {
          grid-column: span 2;
        }

        .analysis-card-medium {
          grid-column: span 1;
        }

        .procedure-summary {
          display: flex;
          align-items: baseline;
          gap: 8px;
          margin: 10px 0 14px;
        }

        .procedure-summary strong {
          font-size: 24px;
          line-height: 1;
          font-weight: 700;
        }

        .procedure-summary span {
          color: #6a6e68;
          font-size: 11px;
          line-height: 1.35;
        }

        @media (max-width: 1280px) {
          .analysis-card-wide,
          .analysis-card-medium {
            grid-column: span 1;
          }
        }
      `}</style>
    </>
  );
}
