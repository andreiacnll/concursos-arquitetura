"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileSearch2,
  FileText,
  Layers3,
} from "lucide-react";
import ProjectMap from "../mapa/ProjectMap";
import {
  buildUniversalContract,
  buildUniversalSubmission,
  cleanUniversal,
  getProcedureAnalysis,
} from "@/lib/analysis-universal";

type Props = {
  ficha: any;
};

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

function itemTitle(item: any): string {
  return cleanUniversal(item);
}

function countLabel(
  value: number,
  singular: string,
  pluralValue: string,
): string {
  if (!value) return "Por confirmar";
  return `${value} ${value === 1 ? singular : pluralValue}`;
}

export default function ProjectInfoPanel({ ficha }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  const toggle = (id: string) => {
    setOpen((current) => (current === id ? null : id));
  };

  const procedure = getProcedureAnalysis(ficha);
  const submission = buildUniversalSubmission(ficha, procedure);
  const contract = buildUniversalContract(ficha, procedure);

  const submissionItems = [
    submission.participantDocuments.length
      ? countLabel(
          submission.participantDocuments.length,
          "documento do concorrente",
          "documentos do concorrente",
        )
      : "",
    submission.proposalDocuments.length
      ? countLabel(
          submission.proposalDocuments.length,
          "elemento técnico",
          "elementos técnicos",
        )
      : "",
    submission.formatsAndLimits.length
      ? countLabel(
          submission.formatsAndLimits.length,
          "regra de submissão",
          "regras de submissão",
        )
      : "",
    ...submission.criticalConditions
      .slice(0, 3)
      .map(itemTitle)
      .filter(Boolean),
  ].filter(Boolean);

  const postSelectionItems = submission.postSelectionDocuments
    .map(itemTitle)
    .filter(Boolean);

  const phases = Array.isArray(contract?.phases) ? contract.phases : [];
  const specialties = Array.isArray(contract?.specialties)
    ? contract.specialties
    : [];
  const deliverables = Array.isArray(contract?.deliverables)
    ? contract.deliverables
    : [];

  const contractItems = [
    phases.length
      ? countLabel(phases.length, "fase de projeto", "fases de projeto")
      : "",
    specialties.length
      ? countLabel(
          specialties.length,
          "especialidade",
          "especialidades",
        )
      : "",
    ...deliverables.slice(0, 5).map(itemTitle).filter(Boolean),
  ].filter(Boolean);

  const coverageItems = [
    submission.documentsRead
      ? countLabel(
          submission.documentsRead,
          "documento lido",
          "documentos lidos",
        )
      : "",
    ...submission.sourceDocuments
      .slice(0, 5)
      .map(itemTitle)
      .filter(Boolean),
    submission.sourceVersion
      ? `Estrutura: ${submission.sourceVersion}`
      : "",
  ].filter(Boolean);

  const officialUrl =
    ficha?.identificacao?.url_base ??
    ficha?.identificacao?.link ??
    ficha?.url_base ??
    ficha?.link ??
    "";

  const location = ficha?.localizacao ?? {};

  return (
    <aside className="project-info-panel">
      <ExpandableCard
        id="submissao"
        icon={<ClipboardCheck size={18} />}
        title="Resumo da submissão"
        description="Elementos efetivamente identificados nas peças."
        count={
          submission.participantDocuments.length ||
          submission.proposalDocuments.length
            ? countLabel(
                submission.participantDocuments.length +
                  submission.proposalDocuments.length,
                "elemento",
                "elementos",
              )
            : "Por confirmar"
        }
        open={open}
        toggle={toggle}
        items={submissionItems}
      />

      <ExpandableCard
        id="pos-selecao"
        icon={<FileText size={18} />}
        title="Após seleção"
        description="Documentos pedidos ao concorrente selecionado."
        count={countLabel(
          submission.postSelectionDocuments.length,
          "documento",
          "documentos",
        )}
        open={open}
        toggle={toggle}
        items={postSelectionItems}
      />

      <ExpandableCard
        id="contrato"
        icon={<BriefcaseBusiness size={18} />}
        title="Âmbito do contrato"
        description="Fases, especialidades e entregáveis confirmados."
        count={
          phases.length || specialties.length || deliverables.length
            ? countLabel(
                phases.length + specialties.length + deliverables.length,
                "elemento",
                "elementos",
              )
            : "Por confirmar"
        }
        open={open}
        toggle={toggle}
        items={contractItems}
      />

      <ExpandableCard
        id="cobertura"
        icon={<FileSearch2 size={18} />}
        title="Cobertura documental"
        description="Peças efetivamente lidas para produzir esta análise."
        count={
          submission.documentsRead
            ? countLabel(
                submission.documentsRead,
                "documento",
                "documentos",
              )
            : "Por confirmar"
        }
        open={open}
        toggle={toggle}
        items={coverageItems}
      />

      <section className="project-summary">
        <div className="info-card-icon">
          <Layers3 size={18} />
        </div>

        <h3>Sobre o projeto</h3>

        <p>
          {ficha?.identificacao?.titulo ||
            "Informação não disponível"}
        </p>

        {location?.morada ? (
          <strong>📍 {location.morada}</strong>
        ) : null}

        {location?.cidade ? <span>{location.cidade}</span> : null}

        {location?.latitude && location?.longitude ? (
          <ProjectMap
            latitude={location.latitude}
            longitude={location.longitude}
          />
        ) : null}

        {officialUrl ? (
          <a
            className="map-button"
            href={officialUrl}
            target="_blank"
            rel="noreferrer"
          >
            Ver fonte oficial ↗
          </a>
        ) : null}
      </section>
    </aside>
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
