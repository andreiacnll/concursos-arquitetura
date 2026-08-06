"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileSearch2,
  Scale,
  ShieldAlert,
} from "lucide-react";

type Props = { ficha: any };

type ExpandableCardProps = {
  id: string;
  icon: ReactNode;
  title: string;
  description: string;
  count: string;
  open: string | null;
  toggle: (id: string) => void;
  items: string[];
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(clean).filter(Boolean).join(" · ");
  if (typeof value === "object") {
    const item = value as Record<string, unknown>;
    return clean(
      item.value ??
        item.normalized_value ??
        item.title ??
        item.label ??
        item.name ??
        item.description ??
        "",
    );
  }
  return "";
}

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function plural(value: number, singular: string, pluralValue: string): string {
  return `${value} ${value === 1 ? singular : pluralValue}`;
}

function fact(extraction: any, key: string): string {
  return clean(extraction?.facts?.[key]);
}

function requirementTitle(item: any): string {
  return clean(
    item?.title ?? item?.label ?? item?.name ?? item?.description,
  );
}

function requirementDetail(item: any): string {
  const details = [
    clean(item?.format),
    clean(item?.page_size ?? item?.size),
    clean(item?.orientation),
    item?.quantity ? `${item.quantity} un.` : "",
    item?.max_pages ? `máx. ${item.max_pages} páginas` : "",
    clean(item?.max_file_size ?? item?.maximum_file_size),
  ].filter(Boolean);

  const title = requirementTitle(item);
  return details.length ? `${title}: ${details.join(" · ")}` : title;
}

export default function ProjectInfoPanel({ ficha }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const toggle = (id: string) => {
    setOpen((current) => (current === id ? null : id));
  };

  const extraction = ficha?.design_competition_extraction ?? {};
  const requirements =
    ficha?.submission_requirements ??
    extraction?.submission_requirements ??
    {};

  const groups = requirements?.groups ?? {};
  const counts = requirements?.counts ?? {};
  const submission = extraction?.submission ?? {};
  const contract = extraction?.contract ?? {};

  const participantDocuments = asArray(groups?.participant_documents);
  const designWork = asArray(groups?.design_work);
  const complementaryDocuments = asArray(groups?.complementary_documents);
  const postSelectionDocuments = asArray(groups?.post_selection_documents);
  const contractDeliverables = asArray(groups?.contract_deliverables);

  const participantCount =
    asNumber(counts?.participant_documents) || participantDocuments.length;
  const deliveryTypeCount =
    asNumber(counts?.competition_delivery_types) ||
    designWork.length + complementaryDocuments.length;
  const physicalUnits = asNumber(counts?.physical_units);
  const digitalFiles = asNumber(counts?.digital_files);
  const postSelectionCount =
    asNumber(counts?.post_selection_documents) ||
    postSelectionDocuments.length;
  const contractCount =
    asNumber(counts?.contract_deliverables) ||
    contractDeliverables.length;
  const specialtyCount = asNumber(contract?.specialty_count);
  const documentsRead =
    asNumber(requirements?.documents_read) ||
    asNumber(extraction?.counts?.documents);
  const sourceDocuments = asArray(requirements?.source_documents_used);
  const sections = asArray(requirements?.sections);

  const submissionItems = [
    plural(
      participantCount,
      "documento do concorrente",
      "documentos do concorrente",
    ),
    plural(deliveryTypeCount, "tipo de entrega", "tipos de entrega"),
    plural(physicalUnits, "unidade física", "unidades físicas"),
    plural(digitalFiles, "ficheiro digital", "ficheiros digitais"),
  ];

  const criticalItems = [
    clean(submission?.anonymity)
      ? `Anonimato: ${clean(submission.anonymity)}`
      : "",
    fact(extraction, "submission_platform")
      ? `Plataforma: ${fact(extraction, "submission_platform")}`
      : "",
    fact(extraction, "submission_deadline")
      ? `Prazo: ${fact(extraction, "submission_deadline")}`
      : "",
    ...designWork.map(requirementDetail).filter(Boolean).slice(0, 7),
  ].filter(Boolean);

  const criteriaDetail =
    clean(ficha?.criterio_detalhe) ||
    clean(ficha?.criterios?.detalhe) ||
    clean(ficha?.criterio_resumo) ||
    clean(ficha?.criterios?.resumo);

  const evaluationItems = criteriaDetail
    ? criteriaDetail
        .split(/\s*[;•]\s*/)
        .map((item) => item.trim())
        .filter(Boolean)
        .slice(0, 8)
    : [];

  const selectedItems = [
    ...postSelectionDocuments.map(requirementTitle).filter(Boolean),
    ...contractDeliverables.map(requirementTitle).filter(Boolean),
    specialtyCount
      ? plural(
          specialtyCount,
          "especialidade prevista",
          "especialidades previstas",
        )
      : "",
  ].filter(Boolean);

  const coverageItems = [
    documentsRead
      ? plural(documentsRead, "documento lido", "documentos lidos")
      : "",
    sourceDocuments.length
      ? plural(
          sourceDocuments.length,
          "fonte utilizada",
          "fontes utilizadas",
        )
      : "",
    sections.length
      ? plural(
          sections.length,
          "secção estruturada",
          "secções estruturadas",
        )
      : "",
    clean(requirements?.version)
      ? `Extrator: ${clean(requirements.version)}`
      : "",
  ].filter(Boolean);

  return (
    <div className="project-info-panel">
      <ExpandableCard
        id="submissao"
        icon={<ClipboardCheck size={18} />}
        title="Resumo da submissão"
        description="Candidatura e peças que têm de ser entregues."
        count={plural(deliveryTypeCount, "tipo", "tipos")}
        open={open}
        toggle={toggle}
        items={submissionItems}
      />
      <ExpandableCard
        id="condicoes"
        icon={<ShieldAlert size={18} />}
        title="Condições críticas"
        description="Regras formais que devem ser confirmadas antes da entrega."
        count={plural(criticalItems.length, "regra", "regras")}
        open={open}
        toggle={toggle}
        items={criticalItems}
      />
      <ExpandableCard
        id="avaliacao"
        icon={<Scale size={18} />}
        title="Modelo de avaliação"
        description="Critérios usados pelo júri para ordenar os trabalhos."
        count={
          evaluationItems.length
            ? plural(evaluationItems.length, "critério", "critérios")
            : "Por confirmar"
        }
        open={open}
        toggle={toggle}
        items={evaluationItems}
      />
      <ExpandableCard
        id="selecionado"
        icon={<BriefcaseBusiness size={18} />}
        title="Se for selecionado"
        description="Habilitação e obrigações do contrato posterior."
        count={plural(
          postSelectionCount + contractCount,
          "elemento",
          "elementos",
        )}
        open={open}
        toggle={toggle}
        items={selectedItems}
      />
      <ExpandableCard
        id="cobertura"
        icon={<FileSearch2 size={18} />}
        title="Cobertura documental"
        description="Peças efetivamente usadas nesta análise."
        count={
          documentsRead
            ? plural(documentsRead, "documento", "documentos")
            : "Por confirmar"
        }
        open={open}
        toggle={toggle}
        items={coverageItems}
      />
    </div>
  );
}

function ExpandableCard({
  id,
  icon,
  title,
  description,
  count,
  open,
  toggle,
  items,
}: ExpandableCardProps) {
  const isOpen = open === id;
  const safeItems = items.filter(Boolean);

  return (
    <article className={`info-card ${isOpen ? "active" : ""}`}>
      <button
        className="info-card-button"
        type="button"
        onClick={() => toggle(id)}
        aria-expanded={isOpen}
      >
        <div className="info-card-icon">{icon}</div>
        <div className="info-card-content">
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        <div className="info-card-count">
          <span>{count}</span>
          <b>{isOpen ? "⌃" : "›"}</b>
        </div>
      </button>

      {isOpen ? (
        <div className="info-card-details">
          {safeItems.length ? (
            safeItems.map((item, index) => (
              <div key={`${id}-${index}`}>✓ {item}</div>
            ))
          ) : (
            <div>Informação ainda não confirmada nas peças.</div>
          )}
        </div>
      ) : null}
    </article>
  );
}
