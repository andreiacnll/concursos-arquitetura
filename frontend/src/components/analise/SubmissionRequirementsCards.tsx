"use client";

import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, FileCheck2, ListChecks } from "lucide-react";

type RequirementItem = {
  key?: string;
  title?: string;
  group?: string;
  category?: string;
  mandatory?: boolean | null;
  conditional?: boolean;
  prohibited?: boolean;
  delivery_mode?: string | null;
  format?: string | null;
  page_size?: string | null;
  orientation?: string | null;
  quantity?: number | null;
  maximum_pages?: number | null;
  maximum_size_mb?: number | null;
  filename?: string | null;
};

type Requirements = {
  groups?: {
    participant_documents?: RequirementItem[];
    design_work?: RequirementItem[];
    complementary_documents?: RequirementItem[];
    post_selection_documents?: RequirementItem[];
  };
};

type Props = { requirements?: Requirements };

const GROUP_LABELS: Record<string, string> = {
  participant_documents: "Documentos do concorrente",
  design_work: "Trabalho de conceção",
  complementary_documents: "Documentos complementares",
  post_selection_documents: "Após seleção",
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function unique(items: RequirementItem[]): RequirementItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${clean(item.group)}::${clean(item.key) || clean(item.title)}`;
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
  if (item.prohibited) parts.push("não permitido");
  if (item.quantity) parts.push(`${item.quantity} un.`);
  if (item.page_size) parts.push(item.page_size);
  if (item.orientation) parts.push(item.orientation);
  if (item.format) parts.push(item.format);
  if (item.maximum_pages) parts.push(`máx. ${item.maximum_pages} páginas`);
  if (item.maximum_size_mb) parts.push(`máx. ${item.maximum_size_mb} MB`);
  if (item.delivery_mode) parts.push(formatMode(item.delivery_mode));
  if (item.filename) parts.push(item.filename);
  if (item.conditional) parts.push("se aplicável");
  else if (item.mandatory === true) parts.push("obrigatório");
  return parts.join(" · ");
}

function RequirementRows({ items, limit }: { items: RequirementItem[]; limit?: number }) {
  const visible = typeof limit === "number" ? items.slice(0, limit) : items;
  if (!visible.length) return <p className="dc-empty">Não identificado nas peças analisadas.</p>;
  return (
    <div className="dc-rows">
      {visible.map((item, index) => (
        <div className="dc-row" key={`${item.key || item.title || "item"}-${index}`}>
          <span>{clean(item.title) || "Documento"}</span>
          <strong>{itemDetails(item) || "Exigido nas peças"}</strong>
        </div>
      ))}
    </div>
  );
}

function DetailSections({ sections }: { sections: Array<{ key: string; items: RequirementItem[] }> }) {
  return (
    <div className="submission-requirements-detail">
      {sections.map((section) => (
        <Fragment key={section.key}>
          <h4>{GROUP_LABELS[section.key]}</h4>
          <RequirementRows items={section.items} />
        </Fragment>
      ))}
    </div>
  );
}

function ToggleButton({ open, setOpen }: { open: boolean; setOpen: (value: boolean) => void }) {
  return (
    <button type="button" className="submission-requirements-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
      {open ? "Ocultar detalhe" : "Ver lista completa"}
      {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
    </button>
  );
}

export default function SubmissionRequirementsCards({ requirements }: Props) {
  const [participantOpen, setParticipantOpen] = useState(false);
  const [deliveryOpen, setDeliveryOpen] = useState(false);
  const groups = requirements?.groups || {};
  const participant = useMemo(() => unique(groups.participant_documents || []), [groups.participant_documents]);
  const design = useMemo(() => unique(groups.design_work || []), [groups.design_work]);
  const complementary = useMemo(() => unique(groups.complementary_documents || []), [groups.complementary_documents]);
  const postSelection = useMemo(() => unique(groups.post_selection_documents || []), [groups.post_selection_documents]);
  const deliveryTotal = design.length + complementary.length;
  const detailTotal = deliveryTotal + postSelection.length;
  return (
    <>
      <article className="dc-card">
        <div className="dc-card-title">
          <FileCheck2 size={18} />
          <h3>Documentos do concorrente</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{participant.length}</strong>
          <span>{participant.length === 1 ? "documento identificado" : "documentos identificados"}</span>
        </div>
        <RequirementRows items={participant} limit={participantOpen ? undefined : 4} />
        {participant.length > 4 ? <ToggleButton open={participantOpen} setOpen={setParticipantOpen} /> : null}
      </article>

      <article className="dc-card">
        <div className="dc-card-title">
          <ListChecks size={18} />
          <h3>Peças e documentos da entrega</h3>
        </div>
        <div className="submission-requirements-summary">
          <strong>{deliveryTotal}</strong>
          <span>tipos de entrega identificados</span>
        </div>
        {!deliveryOpen ? (
          <RequirementRows items={[...design, ...complementary]} limit={5} />
        ) : (
          <DetailSections
            sections={[
              { key: "design_work", items: design },
              { key: "complementary_documents", items: complementary },
              { key: "post_selection_documents", items: postSelection },
            ].filter((section) => section.items.length)}
          />
        )}
        {detailTotal > 0 ? <ToggleButton open={deliveryOpen} setOpen={setDeliveryOpen} /> : null}
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
      `}</style>
    </>
  );
}
