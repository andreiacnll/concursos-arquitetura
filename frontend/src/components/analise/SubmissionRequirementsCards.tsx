"use client";

import { Fragment, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  FileType2,
  ListChecks,
  ShieldAlert,
} from "lucide-react";
import { formatAnalysisItemForDisplay } from "@/lib/analysis-display";

type RequirementItem = {
  key?: string;
  title?: string;
  group?: string;
  category?: string;
  effect?: string;
  phase?: string;
  mandatory?: boolean | null;
  conditional?: boolean;
  prohibited?: boolean;
  severity?: string;
  delivery_mode?: string | null;
  format?: string | null;
  page_size?: string | null;
  orientation?: string | null;
  quantity?: number | null;
  maximum_pages?: number | null;
  recommended_pages?: number | null;
  maximum_size_mb?: number | null;
  filename?: string | null;
  absolute_weight?: number | null;
  detail?: string | null;
  detalhe?: string | null;
  source_text?: string | null;
  source_excerpt?: string | null;
  evidence_excerpt?: string | null;
  summary?: string | null;
  recommended_action?: string | null;
  source_document?: string | null;
  source_heading?: string | null;
  status_label?: string | null;
  status?: string | null;
};

type Requirements = {
  analysis_family?: string;
  groups?: {
    participant_documents?: RequirementItem[];
    design_work?: RequirementItem[];
    complementary_documents?: RequirementItem[];
    post_selection_documents?: RequirementItem[];
    contract_deliverables?: RequirementItem[];
  };
  formats_and_limits?: RequirementItem[];
  critical_conditions?: RequirementItem[];
};

type PhaseAnalysis = {
  family?: string;
  submission?: {
    participant_documents?: RequirementItem[];
    proposal_documents?: RequirementItem[];
    formats_and_limits?: RequirementItem[];
    critical_conditions?: RequirementItem[];
    formal_risks?: RequirementItem[];
    post_selection_documents?: RequirementItem[];
    mandatory_checklist_count?: number;
  };
};

type Props = {
  requirements?: Requirements;
  analysisFamily?: string;
  phaseAnalysis?: PhaseAnalysis;
};

const CATEGORY_LABELS: Record<string, string> = {
  administrative: "Administrativos",
  financial: "Preço e estimativa",
  team_experience: "Equipa e experiência",
  design_submission: "Proposta de conceção",
  optional: "Opcionais",
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function unique(items: RequirementItem[]): RequirementItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${clean(item.category)}::${clean(item.key) || clean(item.title)}`;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function formatMode(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    digital: "digital",
    physical: "físico",
    physical_and_digital: "físico + digital",
    service: "serviço",
  };
  return labels[clean(value)] || clean(value);
}

function itemDetails(item: RequirementItem): string {
  const parts: string[] = [];
  if (item.effect === "explicit_exclusion") parts.push("exclusão explícita");
  if (item.absolute_weight) parts.push(`${item.absolute_weight}% da avaliação`);
  if (item.prohibited) parts.push("não permitido");
  if (item.quantity) parts.push(`${item.quantity} ficheiro${item.quantity === 1 ? "" : "s"}`);
  if (item.page_size) parts.push(item.page_size);
  if (item.orientation) parts.push(item.orientation);
  if (item.format) parts.push(item.format);
  if (item.maximum_pages) parts.push(`máx. ${item.maximum_pages} páginas`);
  if (item.recommended_pages) parts.push(`~${item.recommended_pages} páginas (indicativo)`);
  if (item.maximum_size_mb) parts.push(`máx. ${item.maximum_size_mb} MB`);
  if (item.delivery_mode) parts.push(formatMode(item.delivery_mode));
  if (item.filename) parts.push(item.filename);
  if (item.conditional) parts.push("se aplicável");
  else if (item.mandatory === true && item.effect !== "explicit_exclusion") parts.push("obrigatório");
  else if (item.mandatory === false) parts.push("opcional");
  return parts.join(" · ");
}

function itemDisplay(item: RequirementItem): string {
  return itemDetails(item) ||
    formatAnalysisItemForDisplay(item as Record<string, any>, "document")
      .primaryValue;
}

function itemProvenance(item: RequirementItem): string {
  return clean(
    item.status_label ??
      item.status ??
      item.source_heading ??
      item.source_document,
  ) || "Confirmado nas peças";
}

function RequirementRows({
  items,
  limit,
  warning = false,
}: {
  items: RequirementItem[];
  limit?: number;
  warning?: boolean;
}) {
  const visible = typeof limit === "number" ? items.slice(0, limit) : items;
  if (!visible.length) {
    return <p className="dc-empty">Não identificado nas peças analisadas.</p>;
  }
  return (
    <div className="dc-rows">
      {visible.map((item, index) => (
        <div
          className={warning ? "dc-row submission-warning" : "dc-row"}
          key={`${item.key || item.title || "item"}-${index}`}
        >
          <span>{clean(item.title) || "Elemento"}</span>
          <strong title={itemProvenance(item)}>{itemDisplay(item)}</strong>
        </div>
      ))}
    </div>
  );
}

function GroupedChecklist({ items }: { items: RequirementItem[] }) {
  const groups = Object.entries(CATEGORY_LABELS)
    .map(([key, label]) => ({ key, label, items: items.filter((item) => clean(item.category) === key) }))
    .filter((group) => group.items.length);

  return (
    <div className="submission-requirements-detail">
      {groups.map((group) => (
        <Fragment key={group.key}>
          <h4>{group.label}</h4>
          <RequirementRows items={group.items} />
        </Fragment>
      ))}
    </div>
  );
}

function ToggleButton({
  open,
  setOpen,
  closedLabel = "Ver lista completa",
}: {
  open: boolean;
  setOpen: (value: boolean) => void;
  closedLabel?: string;
}) {
  return (
    <button
      type="button"
      className="submission-requirements-toggle"
      onClick={() => setOpen(!open)}
      aria-expanded={open}
    >
      {open ? "Ocultar detalhe" : closedLabel}
      {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
    </button>
  );
}

export default function SubmissionRequirementsCards({
  requirements,
  analysisFamily,
  phaseAnalysis,
}: Props) {
  const [checklistOpen, setChecklistOpen] = useState(false);
  const [proposalOpen, setProposalOpen] = useState(false);
  const [formatsOpen, setFormatsOpen] = useState(false);
  const [criticalOpen, setCriticalOpen] = useState(false);

  const family =
    clean(analysisFamily) ||
    clean(phaseAnalysis?.family) ||
    clean(requirements?.analysis_family) ||
    "design_competition";
  const isDesignCompetition = family === "design_competition";
  const groups = requirements?.groups || {};
  const submission = phaseAnalysis?.submission || {};

  const checklist = useMemo(
    () => unique(submission.participant_documents || groups.participant_documents || []),
    [submission.participant_documents, groups.participant_documents],
  );
  const proposal = useMemo(
    () => unique(submission.proposal_documents || groups.design_work || []),
    [submission.proposal_documents, groups.design_work],
  );
  const complementary = useMemo(
    () => unique(groups.complementary_documents || []),
    [groups.complementary_documents],
  );
  const formats = useMemo(
    () => unique(submission.formats_and_limits || requirements?.formats_and_limits || []),
    [submission.formats_and_limits, requirements?.formats_and_limits],
  );
  const critical = useMemo(
    () => unique(submission.critical_conditions || requirements?.critical_conditions || []),
    [submission.critical_conditions, requirements?.critical_conditions],
  );

  const mandatoryCount =
    submission.mandatory_checklist_count ??
    checklist.filter((item) => item.mandatory === true && !item.conditional).length;
  const participantTitle = isDesignCompetition
    ? "Documentos do concorrente"
    : "Documentos que instruem a proposta";
  const proposalTitle = isDesignCompetition
    ? "Peças e trabalho de conceção"
    : proposal.length >= 8
      ? "Conteúdo obrigatório do Caderno A3"
      : "Conteúdo técnico da proposta";

  return (
    <>
      <article className="dc-card">
        <div className="dc-card-title">
          <FileCheck2 size={18} />
          <h3>{participantTitle}</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{mandatoryCount}</strong>
          <span>entregas obrigatórias confirmadas</span>
        </div>
        {checklistOpen ? (
          <GroupedChecklist items={checklist} />
        ) : (
          <RequirementRows items={checklist.filter((item) => item.mandatory !== false)} limit={5} />
        )}
        {checklist.length > 5 ? (
          <ToggleButton open={checklistOpen} setOpen={setChecklistOpen} />
        ) : null}
      </article>

      <article className="dc-card">
        <div className="dc-card-title">
          <ListChecks size={18} />
          <h3>{proposalTitle}</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{proposal.length + complementary.length}</strong>
          <span>{proposal.length >= 8 ? "requisitos dentro do Caderno A3" : "conteúdos técnicos exigidos"}</span>
        </div>
        <RequirementRows
          items={[...proposal, ...complementary]}
          limit={proposalOpen ? undefined : 5}
        />
        {proposal.length + complementary.length > 5 ? (
          <ToggleButton open={proposalOpen} setOpen={setProposalOpen} />
        ) : null}
      </article>

      <article className="dc-card">
        <div className="dc-card-title">
          <FileType2 size={18} />
          <h3>Formatos e submissão</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{formats.length}</strong>
          <span>regras verificadas</span>
        </div>
        <RequirementRows items={formats} limit={formatsOpen ? undefined : 4} />
        {formats.length > 4 ? (
          <ToggleButton open={formatsOpen} setOpen={setFormatsOpen} />
        ) : null}
      </article>

      <article className="dc-card">
        <div className="dc-card-title">
          {critical.length ? <AlertTriangle size={18} /> : <ShieldAlert size={18} />}
          <h3>Exclusões explícitas</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{critical.length}</strong>
          <span>causas adicionais no Programa do Concurso</span>
        </div>
        <RequirementRows
          items={critical}
          limit={criticalOpen ? undefined : 4}
          warning
        />
        {critical.length > 4 ? (
          <ToggleButton open={criticalOpen} setOpen={setCriticalOpen} />
        ) : null}
      </article>

      <style jsx>{`
        .submission-requirements-summary {
          display: flex;
          align-items: baseline;
          gap: 8px;
          margin: 14px 0 4px;
          color: #656a62;
        }
        .submission-requirements-summary strong {
          color: #1f231d;
          font-size: 24px;
        }
        .submission-requirements-summary span {
          font-size: 11px;
        }
        .submission-requirements-detail {
          display: grid;
          gap: 12px;
          margin-top: 12px;
        }
        .submission-requirements-detail h4 {
          margin: 8px 0 0;
          padding-top: 10px;
          border-top: 1px solid #e2e3dd;
          font-size: 11px;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          color: #6d716a;
        }
        .submission-requirements-toggle {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-top: 14px;
          padding: 0;
          border: 0;
          background: transparent;
          color: #587436;
          font: inherit;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
        }
        :global(.dc-row span),
        :global(.dc-row strong) {
          display: block;
          overflow: visible;
          white-space: normal;
          overflow-wrap: anywhere;
          word-break: normal;
          line-height: 1.35;
        }
        :global(.submission-warning strong) {
          color: #9b4a32;
        }
      `}</style>
    </>
  );
}
