"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckSquare,
  ClipboardCheck,
  FileCheck2,
  FileText,
  ListChecks,
  MapPin,
  Sparkles,
  Trophy,
  Users,
} from "lucide-react";

type Item = { label: string; value: string; status?: string };
type Evidence = {
  evidence_id: string;
  source_document?: string;
  page?: number | null;
  section?: string;
  excerpt?: string;
  confidence?: number | null;
};
type Card = {
  type: string;
  title: string;
  summary: string;
  items: Item[];
  evidence_ids?: string[];
};
type Insight = {
  title: string;
  summary: string;
  severity?: string;
  status?: string;
  evidence_ids?: string[];
};

export type AnalysisPresentation = {
  document_status: string;
  executive_summary: string;
  cards: Card[];
  risks: Insight[];
  opportunities: Insight[];
  checklist: Insight[];
  missing_information: string[];
  warnings: string[];
  evidence?: Evidence[];
  competition_type?: string;
  competition_subtype?: string;
  classification_confidence?: number;
  classification_reasons?: string[];
  recommended_section_order?: string[];
  section_visibility?: Record<string, boolean>;
  section_priority?: Record<string, number>;
  special_features?: string[];
};

type DisplayCard = {
  key: string;
  type: string;
  title: string;
  summary: string;
  items: Item[];
  icon: ReactNode;
  evidenceIds: string[];
};

const CARD_ICONS: Record<string, ReactNode> = {
  competition_model: <FileText size={18} />,
  contract_scope: <FileText size={18} />,
  context_location: <MapPin size={18} />,
  awards: <Trophy size={18} />,
  jury: <Users size={18} />,
  award_criteria: <ClipboardCheck size={18} />,
  financial_conditions: <Sparkles size={18} />,
  required_team: <Users size={18} />,
  technical_specialties: <Users size={18} />,
  phases_and_deliverables: <ListChecks size={18} />,
  deliverables: <ListChecks size={18} />,
  submission_deliverables: <CheckSquare size={18} />,
  submission_checklist: <FileCheck2 size={18} />,
  anonymity: <FileCheck2 size={18} />,
  calendar: <CalendarDays size={18} />,
  program: <FileText size={18} />,
  risks: <AlertTriangle size={18} />,
  evaluation: <ClipboardCheck size={18} />,
};

const COMPETITION_LABELS: Record<string, string> = {
  design_competition: "Concurso de conceção",
  ideas_competition: "Concurso de ideias",
  execution_project: "Projeto de execução",
  architectural_services: "Serviços de arquitetura",
  rehabilitation_project: "Reabilitação",
  urban_planning: "Planeamento urbano",
  landscape_architecture: "Arquitetura paisagista",
  public_equipment: "Equipamento público",
  framework_agreement: "Acordo quadro",
  works_contract: "Empreitada / obra",
  generic_services: "Serviços",
  unknown: "Tipologia por confirmar",
};

function text(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim();
}

function evidenceKeyIds(ids: string[] | undefined) {
  return Array.isArray(ids) ? ids.filter(Boolean) : [];
}

function iconFor(card: Card): ReactNode {
  return CARD_ICONS[card.type] || <FileText size={18} />;
}

function localizedStatusLabel(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "complete") return "Documentação completa";
  if (normalized === "partial") return "Documentação parcial";
  if (normalized === "insufficient") return "Documentação limitada";
  if (normalized === "announcement_only") return "Apenas anúncio";
  return "Documentação limitada";
}

function missingLabel(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized.includes("checklist") || normalized.includes("submission")) return "Documentos de proposta";
  if (normalized.includes("habilitation") || normalized.includes("qualification") || normalized.includes("administr") || normalized.includes("team")) return "Documentos de habilitação";
  if (normalized.includes("deliver") || normalized.includes("phase") || normalized.includes("contract")) return "Entregáveis contratuais";
  if (normalized.includes("technical")) return "Requisitos técnicos";
  return "Detalhes do procedimento";
}

function safeLabel(value: string) {
  if (!value) return "Requisito";
  return value.replace(/_/g, " ").trim().replace(/^./, (char) => char.toUpperCase());
}

function evidenceLabel(evidence?: Evidence | null) {
  if (!evidence) return "Origem por confirmar";
  const parts = [
    evidence.source_document,
    evidence.section,
    evidence.page ? `p. ${evidence.page}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Origem por confirmar";
}

function evidenceExcerpt(evidence?: Evidence | null) {
  if (!evidence?.excerpt) return "";
  return evidence.excerpt.length > 240 ? `${evidence.excerpt.slice(0, 237)}...` : evidence.excerpt;
}

function cardOrderIndex(order: string[] | undefined) {
  const map = new Map<string, number>();
  (order || []).forEach((key, index) => map.set(key, index));
  return map;
}

function buildDisplayCards(data: AnalysisPresentation): DisplayCard[] {
  const order = cardOrderIndex(data.recommended_section_order);
  const cards = (data.cards || [])
    .filter((card) => text(card.title) && (card.items?.length || text(card.summary)))
    .map((card, index) => ({
      key: `${card.type || "card"}-${index}`,
      type: card.type || "card",
      title: card.title,
      summary: text(card.summary),
      items: (card.items || []).filter((item) => text(item.label) && text(item.value)),
      icon: iconFor(card),
      evidenceIds: evidenceKeyIds(card.evidence_ids),
    }))
    .sort((a, b) => {
      const ai = order.has(a.type) ? order.get(a.type)! : 999 + a.key.length;
      const bi = order.has(b.type) ? order.get(b.type)! : 999 + b.key.length;
      return ai - bi;
    });

  return cards;
}

function highlightCards(cards: DisplayCard[]) {
  return cards
    .filter((card) => card.items.length > 0)
    .slice(0, 4)
    .map((card) => ({
      title: card.title,
      value: card.items[0]?.value || card.summary,
    }));
}

function EvidenceDetail({ evidence }: { evidence?: Evidence | null }) {
  if (!evidence) return null;
  return (
    <div className="presentation-evidence-detail">
      <span>{evidenceLabel(evidence)}</span>
      {typeof evidence.confidence === "number" ? <span>Confiança: {Math.round(evidence.confidence * 100)}%</span> : null}
      {evidenceExcerpt(evidence) ? <p>{evidenceExcerpt(evidence)}</p> : null}
    </div>
  );
}

function PresentationCardView({
  card,
  evidenceMap,
}: {
  card: DisplayCard;
  evidenceMap: Map<string, Evidence>;
}) {
  const [open, setOpen] = useState(false);
  const visibleLimit = card.type === "risks" ? 3 : 4;
  const visibleItems = open ? card.items : card.items.slice(0, visibleLimit);
  const hasDetail = card.items.length > visibleLimit || card.evidenceIds.length > 0;
  const details = card.evidenceIds
    .map((id) => evidenceMap.get(id))
    .filter(Boolean) as Evidence[];

  return (
    <article className="document-card">
      <div className="document-card-heading">
        <span className="document-card-icon">{card.icon}</span>
        <div className="document-card-titleblock">
          <h3>{card.title}</h3>
          {card.type === "risks" ? <span className="presentation-card-note">Riscos confirmados</span> : null}
        </div>
      </div>
      {card.summary ? <p className="presentation-v2-card-summary">{card.summary}</p> : null}
      <div id={`presentation-card-${card.key}`} className="document-card-body">
        {visibleItems.length > 0 ? (
          <ul className="document-list presentation-v2-items">
            {visibleItems.map((item, index) => (
              <li key={`${card.key}-${item.label}-${index}`}>
                <strong>{safeLabel(item.label)}</strong>
                <span>{item.value}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {open && details.length > 0 ? (
          <div className="presentation-evidence-list">
            {details.map((evidence) => (
              <EvidenceDetail key={evidence.evidence_id} evidence={evidence} />
            ))}
          </div>
        ) : null}
      </div>
      {hasDetail ? (
        <button
          type="button"
          className="document-card-toggle"
          aria-expanded={open}
          aria-controls={`presentation-card-${card.key}`}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Ocultar detalhe" : card.items.length > visibleLimit ? "Ver todos" : "Ver detalhe"}
        </button>
      ) : null}
    </article>
  );
}

function buildInsightCard(title: string, items: Insight[], key: string, icon: ReactNode): DisplayCard | null {
  const usable = items.filter((item) => text(item.title) && text(item.summary));
  if (!usable.length) return null;
  return {
    key,
    type: key,
    title,
    summary: usable.length === 1 ? usable[0].summary : `${usable.length} pontos identificados nas peças analisadas.`,
    items: usable.map((item) => ({ label: item.title, value: item.summary })),
    icon,
    evidenceIds: usable.flatMap((item) => item.evidence_ids || []),
  };
}

export function PresentationExecutiveSummary({ data }: { data: AnalysisPresentation }) {
  const cards = buildDisplayCards(data);
  const highlights = highlightCards(cards);
  const typeLabel = data.competition_type ? COMPETITION_LABELS[data.competition_type] || safeLabel(data.competition_type) : "";
  const subtypeLabel = data.competition_subtype ? safeLabel(data.competition_subtype) : "";

  if (!text(data.executive_summary) && !highlights.length && !typeLabel) {
    return null;
  }

  return (
    <section className="presentation-executive-summary" aria-label="Resumo executivo">
      <div className="presentation-executive-header">
        <span>Resumo executivo</span>
        <h2>{typeLabel || "Informação extraída das peças"}</h2>
        {text(data.executive_summary) ? <p>{data.executive_summary}</p> : null}
        {subtypeLabel ? <p className="presentation-executive-subtype">{subtypeLabel}</p> : null}
      </div>
      {highlights.length > 0 ? (
        <div className="presentation-summary-highlights">
          {highlights.map((item) => (
            <div key={`${item.title}-${item.value}`} className="presentation-summary-highlight">
              <span>{item.title}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function AnalysisPresentationV2({ data }: { data: AnalysisPresentation }) {
  const cards = buildDisplayCards(data);
  const evidenceMap = useMemo(() => new Map((data.evidence || []).map((item) => [item.evidence_id, item] as const)), [data.evidence]);
  const limited = !["complete"].includes((data.document_status || "").toLowerCase());
  const missing = [...new Set((data.missing_information || []).map(missingLabel))].filter(Boolean);
  const extraCards = [
    buildInsightCard("Riscos", data.risks || [], "risks", <AlertTriangle size={18} />),
    buildInsightCard("Oportunidades", data.opportunities || [], "opportunities", <Trophy size={18} />),
    buildInsightCard("Checklist", data.checklist || [], "checklist", <CheckSquare size={18} />),
  ].filter(Boolean) as DisplayCard[];

  const allCards = [...cards];
  const existingTypes = new Set(cards.map((card) => card.type));
  for (const card of extraCards) {
    if (!existingTypes.has(card.type)) {
      allCards.push(card);
    }
  }

  return (
    <section className="document-insights-section presentation-v2" aria-label="Informação extraída das peças">
      <div className="document-insights-header">
        <span>Apresentação documental</span>
        <h2>Informação extraída das peças</h2>
        <p>{limited ? "A análise foi realizada com documentação limitada. Alguns pontos permanecem por confirmar." : data.executive_summary}</p>
        {data.competition_type ? (
          <p className="presentation-type-line">
            {COMPETITION_LABELS[data.competition_type] || safeLabel(data.competition_type)}
            {data.competition_subtype ? ` · ${safeLabel(data.competition_subtype)}` : ""}
          </p>
        ) : null}
      </div>

      {allCards.length > 0 ? (
        <div className="document-insights-grid">
          {allCards.map((card) => (
            <PresentationCardView key={card.key} card={card} evidenceMap={evidenceMap} />
          ))}
        </div>
      ) : null}

      {missing.length > 0 ? (
        <div className="presentation-v2-missing">
          <h3>Informação ainda por confirmar</h3>
          <div className="presentation-v2-chips">
            {missing.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
