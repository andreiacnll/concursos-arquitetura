"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  CalendarDays,
  ClipboardCheck,
  FileCheck2,
  FileText,
  ListChecks,
  Users,
} from "lucide-react";
import { truncateAtSentenceBoundary } from "@/lib/text-summary";

type Evidence = {
  value?: string;
  source_document?: string;
  page?: number | null;
  section?: string;
  confidence?: number;
  status?: string;
  evidence_excerpt?: string;
};

type Props = {
  insights?: any;
};

function valueOf(evidence: Evidence | string | null | undefined) {
  if (!evidence) return "";
  if (typeof evidence === "string") return evidence;
  return evidence.value || "";
}

function evidenceLabel(evidence?: Evidence | null) {
  if (!evidence) return "Origem não identificada";
  const parts = [evidence.source_document, evidence.section, evidence.page ? `p. ${evidence.page}` : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Origem não identificada";
}

function EvidenceDetail({ evidence }: { evidence?: Evidence | null }) {
  if (!evidence) return null;
  return (
    <div className="document-evidence">
      <span>{evidenceLabel(evidence)}</span>
      {evidence.evidence_excerpt ? <p>{truncateAtSentenceBoundary(evidence.evidence_excerpt, 260)}</p> : null}
    </div>
  );
}

function DocumentCard({
  id,
  title,
  icon,
  children,
}: {
  id: string;
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className="document-card">
      <div className="document-card-heading">
        <span className="document-card-icon">{icon}</span>
        <h3>{title}</h3>
      </div>
      <div id={`document-card-${id}`} className={open ? "document-card-body is-open" : "document-card-body"}>
        {children}
      </div>
      <button
        type="button"
        className="document-card-toggle"
        aria-expanded={open}
        aria-controls={`document-card-${id}`}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "Ocultar detalhe" : "Ver detalhe"}
      </button>
    </article>
  );
}

function ProcedureSummary({ summary }: { summary: any }) {
  const fields = [
    ["Objeto", summary?.object],
    ["Entidade", summary?.contracting_entity],
    ["Procedimento", summary?.procedure_type],
    ["Preço base", summary?.base_price],
    ["Prazo candidatura", summary?.submission_deadline],
    ["Prazo execução", summary?.execution_deadline],
    ["Localização", summary?.location],
    ["Plataforma", summary?.platform],
  ].filter(([, evidence]) => Boolean(valueOf(evidence as Evidence)));

  if (!fields.length) return null;

  return (
    <DocumentCard id="procedure" title="Resumo do procedimento" icon={<FileText size={18} />}>
      <dl className="document-fields">
        {fields.map(([label, evidence]) => (
          <div key={label as string}>
            <dt>{label}</dt>
            <dd>{valueOf(evidence as Evidence)}</dd>
            <EvidenceDetail evidence={evidence as Evidence} />
          </div>
        ))}
      </dl>
    </DocumentCard>
  );
}

function TimelineCard({ items }: { items: any[] }) {
  const usable = items.filter((item) => valueOf(item));
  if (!usable.length) return null;
  return (
    <DocumentCard id="timeline" title="Calendário do concurso" icon={<CalendarDays size={18} />}>
      <ol className="document-list">
        {usable.map((item, index) => (
          <li key={`${item.type}-${index}`}>
            <strong>{item.type}</strong>
            <span>{item.value}</span>
            <EvidenceDetail evidence={item.evidence} />
          </li>
        ))}
      </ol>
    </DocumentCard>
  );
}

function CriteriaCard({ items }: { items: any[] }) {
  const usable = items.filter((item) => item?.factor || item?.subfactors?.length);
  if (!usable.length) return null;
  return (
    <DocumentCard id="criteria" title="Critérios de adjudicação" icon={<ClipboardCheck size={18} />}>
      <ul className="document-list">
        {usable.map((item, index) => (
          <li key={`${item.factor}-${index}`}>
            <strong>
              {item.factor || "Critério"} {item.weight ? `- ${item.weight}` : ""}
            </strong>
            {item.subfactors?.length ? (
              <ul>
                {item.subfactors.map((sub: any, subIndex: number) => (
                  <li key={subIndex}>{String(sub)}</li>
                ))}
              </ul>
            ) : null}
            <EvidenceDetail evidence={item.evidence} />
          </li>
        ))}
      </ul>
    </DocumentCard>
  );
}

function DeliverablesCard({ items }: { items: any[] }) {
  const usable = items.filter((phase) => phase?.phase || phase?.items?.length);
  if (!usable.length) return null;
  return (
    <DocumentCard id="deliverables" title="Entregáveis e fases" icon={<ListChecks size={18} />}>
      <div className="document-list">
        {usable.map((phase, index) => (
          <section key={`${phase.phase}-${index}`}>
            <strong>{phase.phase || "Fase identificada"}</strong>
            <ul>
              {(phase.items || []).map((item: Evidence, itemIndex: number) => {
                const text = valueOf(item);
                if (!text) return null;
                return (
                  <li key={itemIndex}>
                    {text}
                    <EvidenceDetail evidence={item} />
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </DocumentCard>
  );
}

function RequiredDocumentsCard({ groups }: { groups: any[] }) {
  const usable = groups.filter((group) => group?.group || group?.items?.length);
  if (!usable.length) return null;
  return (
    <DocumentCard id="required-documents" title="Documentos obrigatórios" icon={<FileCheck2 size={18} />}>
      <div className="document-list">
        {usable.map((group, index) => (
          <section key={`${group.group}-${index}`}>
            <strong>{group.group || "Grupo documental"}</strong>
            <ul>
              {(group.items || []).map((item: Evidence, itemIndex: number) => {
                const text = valueOf(item);
                if (!text) return null;
                return (
                  <li key={itemIndex}>
                    {text}
                    <EvidenceDetail evidence={item} />
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </DocumentCard>
  );
}

function RequiredTeamCard({ items }: { items: any[] }) {
  const usable = items.filter((item) => item?.requirement || item?.category);
  if (!usable.length) return null;
  return (
    <DocumentCard id="required-team" title="Equipa exigida" icon={<Users size={18} />}>
      <ul className="document-list">
        {usable.map((item, index) => (
          <li key={`${item.requirement}-${index}`}>
            <strong>{item.category}</strong>
            <span>{item.requirement}</span>
            <EvidenceDetail evidence={item.evidence} />
          </li>
        ))}
      </ul>
    </DocumentCard>
  );
}

export default function DocumentInsightsCards({ insights }: Props) {
  const safe = insights || {};
  const hasAny = useMemo(
    () =>
      Boolean(
        safe.procedure_summary ||
          safe.timeline?.length ||
          safe.award_criteria?.length ||
          safe.deliverables?.length ||
          safe.required_documents?.length ||
          safe.required_team?.length,
      ),
    [safe],
  );

  if (!hasAny) return null;

  return (
    <section className="document-insights-section">
      <div className="document-insights-header">
        <span>Análise documental</span>
        <h2>Informação extraída das peças</h2>
        {safe.limited_documentation_notice ? <p>{safe.limited_documentation_notice}</p> : null}
      </div>
      <div className="document-insights-grid">
        <ProcedureSummary summary={safe.procedure_summary || {}} />
        <TimelineCard items={safe.timeline || []} />
        <CriteriaCard items={safe.award_criteria || []} />
        <DeliverablesCard items={safe.deliverables || []} />
        <RequiredDocumentsCard groups={safe.required_documents || []} />
        <RequiredTeamCard items={safe.required_team || []} />
      </div>
    </section>
  );
}
