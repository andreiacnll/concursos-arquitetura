"use client";

// CNLL_DIRECT_FICHA_CARDS_V17_10

// CNLL_CARDS_MODAL_V17_9B

// CNLL_UNIVERSAL_CARD_SOURCE_V17_7
// CNLL_UNIVERSAL_MERGE_V17_8

import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Building2,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileText,
  Layers3,
  MapPin,
  Sparkles,
  Target,
  Trophy,
} from "lucide-react";
import ProjectInfoPanel from "@/components/analise/dashboard/ProjectInfoPanel";
import { DomainDetailsButton } from "@/components/analise/DesignCompetitionDomainModal";
import FunctionalProgramSummaryCard from "@/components/analise/FunctionalProgramSummaryCard";
import InterventionProgramSummaryCard from "@/components/analise/InterventionProgramSummaryCard";
import UniversalSubmissionCards from "@/components/analise/UniversalSubmissionCards";
import UniversalDecisionCriteria from "@/components/analise/UniversalDecisionCriteria";
import ProcedureSpecificCards from "@/components/analise/ProcedureSpecificCards";
import AnalysisQuestionsModal from "@/components/analise/AnalysisQuestionsModal";

import { buildCriteriaSummary, getProcedureAnalysis, buildProcedureCardAnalysis } from "@/lib/analysis-universal";
import { formatAnalysisItemForDisplay } from "@/lib/analysis-display";
type Props = {
  ficha: any;
  concurso: any;
  presentation?: any;
  concursoId: string;
};

type Fact = {
  label: string;
  value: string;
  confirmed: boolean;
  statusLabel?: string;
};

const EMPTY = "Por confirmar";

const LABELS: Record<string, string> = {
  competition_prize_first: "1.º prémio",
  competition_prize_second: "2.º prémio",
  competition_prize_third: "3.º prémio",
  competition_prize_mentions: "Menções honrosas",
  competition_prize_total: "Total dos prémios",
  procedure_value: "Valor do procedimento",
  estimated_construction_cost: "Custo estimado da obra",
  design_services_value: "Honorários / serviços de projeto",
  submission_panel_quantity: "Painéis",
  submission_panel_format: "Formato dos painéis",
  descriptive_memory: "Memória descritiva",
  digital_files: "Ficheiros digitais",
  anonymity_requirement: "Anonimato",
  submission_platform: "Plataforma",
  submission_deadline: "Prazo de entrega",
  site_visit: "Visita ao local",
  clarification_deadline: "Esclarecimentos",
  execution_project: "Projeto de execução",
  technical_assistance: "Assistência técnica",
  final_drawings: "Telas finais",
  measurements: "Mapa de medições",
  quantity_schedule: "Mapa de quantidades",
  approval_requirement: "Aprovações externas",
  specialties: "Especialidades",
  project_phases: "Fases do projeto",
  payment_conditions: "Condições de pagamento",
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(clean).filter(Boolean).join(" · ");
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return clean(
      obj.value ??
        obj.normalized_value ??
        obj.text ??
        obj.label ??
        obj.name ??
        obj.description ??
        "",
    );
  }
  return "";
}

function compact(value: unknown, limit = 180): string {
  const text = clean(value);
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}…`;
}

function valid(value: string): boolean {
  const normalized = value.toLowerCase();
  return Boolean(
    value &&
      value !== "0" &&
      value !== "0.0" &&
      !normalized.includes("not found") &&
      !normalized.includes("não identificado") &&
      !normalized.includes("nao identificado"),
  );
}

function documentStatusLabel(value: unknown): string {
  const text = clean(value);
  const normalized = normalizeCategory(text);
  if (!text) return "";
  if (["partial", "parcial"].includes(normalized)) return "Parcial";
  if (["success", "completed", "complete", "concluida"].includes(normalized)) {
    return "Completa";
  }
  if (normalized === "announcement_only") return "Apenas anúncio";
  if (normalized === "login_required") return "Acesso condicionado";
  return text;
}

function makeFact(
  label: string,
  value: unknown,
  limit = 150,
  statusLabel?: string,
): Fact {
  const text = compact(value, limit);
  return {
    label,
    value: valid(text) ? text : EMPTY,
    confirmed: valid(text),
    statusLabel: clean(statusLabel) || undefined,
  };
}

function getFact(extraction: any, key: string): string {
  return clean(extraction?.facts?.[key]?.value);
}

function unique(values: unknown[], max = 8): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const value of values) {
    const text = compact(value, 150);
    const signature = text.toLowerCase();
    if (!text || seen.has(signature)) continue;
    seen.add(signature);
    output.push(text);
    if (output.length >= max) break;
  }
  return output;
}

function listValues(value: unknown, max = 6): string[] {
  if (!Array.isArray(value)) return [];
  return unique(
    value.map((item) =>
      item && typeof item === "object"
        ? (item as any).justification ??
          (item as any).explanation ??
          (item as any).description ??
          (item as any).name ??
          item
        : item,
    ),
    max,
  );
}



type OfficialScore = {
  active: boolean;
  displayValue: string;
  suffix: string;
  label: string;
  note: string;
  recommendation: string;
  demonstrated: number | null;
  maximum: number | null;
  pending: number | null;
};

function formatScoreNumber(value: number): string {
  return Math.abs(value - Math.round(value)) < 0.001
    ? String(Math.round(value))
    : value.toFixed(1).replace(".", ",");
}

function resultStatus(value: any): string {
  return normalizeCategory(
    value?.status ?? value?.label ?? value?.status_label ?? value,
  );
}

function buildOfficialScore(ficha: any, awardFit: any): OfficialScore {
  const canonical = ficha?.analysis_canonical || {};
  const requirements = Array.isArray(canonical?.requirements)
    ? canonical.requirements
    : [];
  const factors = Array.isArray(canonical?.criteria?.factors)
    ? canonical.criteria.factors
    : [];

  const eliminatory = requirements.filter((item: any) => {
    const nature = normalizeCategory(item?.nature);
    const stage = normalizeCategory(item?.stage || item?.phase);
    return nature === "eligibility" && stage !== "post award";
  });
  const failed = eliminatory.filter((item: any) => {
    const status = resultStatus(item?.result);
    return status.includes("not met") || status.includes("nao cumpre");
  });
  const unknownEligibility = eliminatory.filter((item: any) => {
    const status = resultStatus(item?.profile || item?.result);
    return !status || status.includes("missing") || status.includes("pending") || status.includes("por confirmar");
  });

  if (failed.length) {
    return {
      active: true,
      displayValue: "Não elegível",
      suffix: "",
      label: "Elegibilidade",
      note: `${failed.length} requisito eliminatório não cumprido.`,
      recommendation: "Há requisitos eliminatórios não cumpridos; a pontuação não deve ser calculada antes de resolver a elegibilidade.",
      demonstrated: null,
      maximum: null,
      pending: null,
    };
  }

  const assessed = Array.isArray(awardFit?.assessed_requirements)
    ? awardFit.assessed_requirements
    : [];

  if (awardFit?.active && assessed.length) {
    const demonstrated = Number(awardFit?.documented_weight || 0);
    const relevant = Number(awardFit?.relevant_weight || 0);
    const pendingRelevant = Number(awardFit?.pending_weight || 0);
    const maximum = relevant > 0 && relevant <= 100 ? 100 : relevant || null;
    const pendingOther = maximum !== null ? Math.max(0, maximum - relevant) : 0;
    const pending = pendingRelevant + pendingOther;
    const high = maximum !== null
      ? Math.min(maximum, demonstrated + pending)
      : null;

    return {
      active: true,
      displayValue: formatScoreNumber(demonstrated),
      suffix: maximum !== null ? `/${formatScoreNumber(maximum)}` : "",
      label: unknownEligibility.length ? "Elegibilidade por confirmar" : "Pontuação demonstrável",
      note: high !== null
        ? `Potencial atual: ${formatScoreNumber(demonstrated)}–${formatScoreNumber(high)} / ${formatScoreNumber(maximum || 100)}.`
        : `${formatScoreNumber(demonstrated)} pontos demonstráveis; restante por avaliar.`,
      recommendation: unknownEligibility.length
        ? `A elegibilidade ainda tem ${unknownEligibility.length} requisito(s) por confirmar. A pontuação demonstrável nos critérios oficiais é ${formatScoreNumber(demonstrated)}${maximum !== null ? `/${formatScoreNumber(maximum)}` : ""}; o restante depende de prova específica e fatores ainda por avaliar.`
        : `Com os factos comprováveis atuais, estão demonstrados ${formatScoreNumber(demonstrated)}${maximum !== null ? `/${formatScoreNumber(maximum)}` : ""} pontos dos critérios oficiais; o restante fica por confirmar ou por avaliar.`,
      demonstrated,
      maximum,
      pending,
    };
  }

  const weightedRequirements = requirements.filter((item: any) => {
    const nature = normalizeCategory(item?.nature);
    const weight = Number(item?.impact_weight_percent || 0);
    const stage = normalizeCategory(item?.stage || item?.phase);
    return stage !== "post award" && weight > 0 && ["team", "evaluation"].includes(nature);
  });

  if (weightedRequirements.length) {
    const officialWeightGroups = new Map<string, { weight: number; statuses: string[] }>();

    for (const item of weightedRequirements) {
      const key = [
        clean(item?.factor_code),
        clean(item?.subfactor_code),
        clean(item?.subfactor_label || item?.label || item?.id),
      ]
        .filter(Boolean)
        .join("|")
        .toLowerCase();

      if (!key) continue;

      const current = officialWeightGroups.get(key) || { weight: 0, statuses: [] };
      current.weight = Math.max(current.weight, Number(item?.impact_weight_percent || 0));
      current.statuses.push(resultStatus(item?.result || item?.profile));
      officialWeightGroups.set(key, current);
    }

    const groups = Array.from(officialWeightGroups.values()).filter(
      (item) => item.weight > 0,
    );
    const maximum = groups.reduce((sum, item) => sum + item.weight, 0);
    const demonstrated = groups.reduce((sum, item) => {
      const statuses = item.statuses.filter(Boolean);
      const hasNotMet = statuses.some(
        (status) =>
          status.includes("not met") ||
          status.includes("nao cumpre") ||
          status.includes("nao demonstrado"),
      );
      const allMet =
        statuses.length > 0 &&
        statuses.every(
          (status) =>
            !hasNotMet &&
            (status.includes("met") ||
              status.includes("cumpre") ||
              status.includes("confirmed") ||
              status.includes("confirmado")),
        );
      return sum + (allMet ? item.weight : 0);
    }, 0);

    return {
      active: true,
      displayValue: formatScoreNumber(demonstrated),
      suffix: maximum ? `/${formatScoreNumber(maximum)}` : "",
      label: unknownEligibility.length ? "Elegibilidade por confirmar" : "Pontuação demonstrável",
      note: `Critérios oficiais parcialmente estruturados por subcritério: ${formatScoreNumber(demonstrated)}–${formatScoreNumber(maximum)} pontos calculáveis.`,
      recommendation: `A experiência/equipa tem critérios oficiais estruturados, mas ainda depende de confirmação específica da empresa. Não foi atribuída pontuação média a fatores por avaliar.`,
      demonstrated,
      maximum,
      pending: Math.max(0, maximum - demonstrated),
    };
  }

  const hasOfficialCriteria = factors.length > 0 || assessed.length > 0;

  return {
    active: hasOfficialCriteria || requirements.length > 0,
    displayValue: "—",
    suffix: "",
    label: unknownEligibility.length ? "Elegibilidade por confirmar" : "Pontuação por confirmar",
    note: hasOfficialCriteria
      ? "Existem critérios oficiais, mas faltam pesos/regras suficientes para calcular pontuação sem heurística."
      : "Sem árvore de critérios oficiais calculável.",
    recommendation: unknownEligibility.length
      ? `Há ${unknownEligibility.length} requisito(s) de elegibilidade por confirmar. A pontuação fica suspensa até haver factos suficientes.`
      : "A leitura identificou informação relevante, mas ainda não há pesos oficiais suficientes para calcular uma pontuação auditável.",
    demonstrated: null,
    maximum: null,
    pending: null,
  };
}
function normalizeCategory(value: unknown): string {
  return clean(value)
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .trim();
}

function categoryAliases(category: string): string[] {
  const normalized = normalizeCategory(category);
  if (normalized.includes("educ") || normalized.includes("escola")) {
    return [
      "educacao",
      "escola",
      "escolar",
      "ensino",
      "school",
      "college",
      "university",
      "universidade",
      "kindergarten",
      "creche",
      "jardim de infancia",
      "centro escolar",
    ];
  }
  if (normalized.includes("habit") || normalized.includes("resid")) {
    return ["habitacao", "residencial", "housing"];
  }
  if (normalized.includes("cultur")) {
    return ["cultura", "cultural"];
  }
  if (normalized.includes("saude") || normalized.includes("hospital")) {
    return ["saude", "hospitalar", "healthcare"];
  }
  return normalized ? [normalized] : [];
}

function findCompanyProjectCount(root: unknown, category: string): number | null {
  const aliases = categoryAliases(category);
  if (!aliases.length) return null;

  let explicitBest = 0;
  const uniqueProjects = new Set<string>();
  const visited = new Set<object>();
  const genericNames = new Set([
    "educacao",
    "education",
    "escola",
    "school",
    "habitacao",
    "housing",
    "cultura",
    "saude",
  ]);

  const visit = (value: unknown, depth = 0) => {
    if (depth > 14 || value === null || value === undefined) return;

    if (Array.isArray(value)) {
      for (const item of value) visit(item, depth + 1);
      return;
    }

    if (typeof value !== "object") return;
    const objectValue = value as Record<string, unknown>;
    if (visited.has(objectValue)) return;
    visited.add(objectValue);

    const fieldName = normalizeCategory(objectValue.field ?? "");
    if (fieldName === "projects.items" || fieldName === "projects items") {
      const memoryValue = objectValue.value;
      if (Array.isArray(memoryValue)) {
        for (const project of memoryValue) visit(project, depth + 1);
      } else if (typeof memoryValue === "string") {
        try {
          visit(JSON.parse(memoryValue), depth + 1);
        } catch {
          const projectName = normalizeCategory(memoryValue);
          if (
            projectName.length >= 4 &&
            aliases.some((alias) => projectName.includes(alias)) &&
            !genericNames.has(projectName)
          ) {
            uniqueProjects.add(projectName);
          }
        }
      }
    }

    const projectName = normalizeCategory(
      objectValue.name ?? objectValue.title ?? objectValue.project_name ?? "",
    );
    const typology = normalizeCategory(
      objectValue.normalized_typology ??
        objectValue.original_typology ??
        objectValue.typology ??
        objectValue.category ??
        objectValue.label ??
        "",
    );
    const combined = `${projectName} ${typology}`.trim();
    const matchesCategory = aliases.some((alias) => combined.includes(alias));

    if (matchesCategory) {
      for (const key of [
        "count",
        "project_count",
        "projects_count",
        "total",
        "quantity",
        "number",
      ]) {
        const candidate = Number(objectValue[key]);
        if (Number.isFinite(candidate) && candidate > explicitBest) {
          explicitBest = Math.round(candidate);
        }
      }

      if (
        projectName &&
        projectName.length >= 4 &&
        !genericNames.has(projectName)
      ) {
        uniqueProjects.add(projectName);
      }
    }

    for (const [key, nested] of Object.entries(objectValue)) {
      const normalizedKey = normalizeCategory(key);
      const keyMatches = aliases.some((alias) => normalizedKey.includes(alias));
      const countKey = /count|total|quantity|number|numero|quantidade/.test(normalizedKey);
      const numeric = Number(nested);
      if (
        keyMatches &&
        countKey &&
        Number.isFinite(numeric) &&
        numeric > explicitBest
      ) {
        explicitBest = Math.round(numeric);
      }
      visit(nested, depth + 1);
    }
  };

  visit(root);
  const inferredFromProjects = uniqueProjects.size;
  const count = Math.max(explicitBest, inferredFromProjects);
  return count > 0 ? count : null;
}

function enrichOpportunityCounts(items: string[], ficha: any): string[] {
  const companyRoot = ficha?.company_context ?? ficha;

  return items.map((item) => {
    const match = item.match(
      /^\s*\d+\s+projetos?\s+em\s+(.+?)\s*$/i,
    );
    if (!match) return item;
    const category = match[1];
    const count = findCompanyProjectCount(companyRoot, category);
    if (!count) return item;
    return `${count} ${count === 1 ? "projeto" : "projetos"} em ${category}`;
  });
}


function FactRows({ items }: { items: Fact[] }) {
  return (
    <div className="dc-rows">
      {items.map((item) => (
        <div className="dc-row" key={`${item.label}-${item.value}`}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

function List({
  items,
  warning = false,
}: {
  items: string[];
  warning?: boolean;
}) {
  if (!items.length) return <p className="dc-empty">{EMPTY}</p>;
  return (
    <ul className={warning ? "dc-list warning" : "dc-list"}>
      {items.map((item) => (
        <li key={item}>
          {warning ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function awardItemCode(item: any): string {
  const direct = clean(
    item?.subfactor_code ??
      item?.criterion_code ??
      item?.code,
  );
  if (direct) return direct.toLowerCase();

  const evidence = clean(
    item?.evidence_excerpt ??
      item?.source_excerpt ??
      item?.name ??
      item?.display_name,
  );
  const match = evidence.match(/\b([A-Z]\d+)\b/i);
  return match ? match[1].toLowerCase() : "";
}

function isWeightOnlyRequirement(text: string): boolean {
  const normalized = normalizeCategory(text);
  return (
    normalized.includes("ponderacao") ||
    normalized.includes("peso parcial")
  );
}

function awardRequirementDetail(
  item: any,
  canonical: any,
): string {
  const requirements = Array.isArray(canonical?.requirements)
    ? canonical.requirements
    : [];
  const code = awardItemCode(item);
  const label = normalizeCategory(
    clean(item?.name) || clean(item?.display_name),
  );

  const linked = requirements.filter((requirement: any) => {
    const reqCode = clean(requirement?.subfactor_code).toLowerCase();
    if (code && reqCode && code === reqCode) return true;

    const reqLabel = normalizeCategory(requirement?.label);
    return Boolean(
      label &&
        reqLabel &&
        (
          label.includes(reqLabel) ||
          reqLabel.includes(label)
        ),
    );
  });

  const preferred = linked
    .map((requirement: any) =>
      formatAnalysisItemForDisplay(requirement, "requirement").primaryValue,
    )
    .filter((text: string) => text && !isWeightOnlyRequirement(text));

  if (preferred.length) return preferred[0];

  const fallback = [
    ...linked.map((requirement: any) =>
      clean(requirement?.required?.text) ||
        clean(requirement?.source?.excerpt),
    ),
    clean(item?.requirement_text),
    clean(item?.source_text),
    clean(item?.description),
    clean(item?.summary),
    clean(item?.evidence_excerpt),
  ].filter(Boolean);

  return fallback.length ? compact(fallback[0], 96) : "Requisito identificado";
}

function awardRequirementProvenance(item: any): string {
  return clean(
    item?.status_label ??
      item?.source_document ??
      item?.source_heading ??
      item?.source?.document,
  ) || "Confirmado nas peças";
}

function AwardFitList({ fit }: { fit: any }) {
  const items = Array.isArray(fit?.assessed_requirements)
    ? fit.assessed_requirements
    : [];
  if (!items.length) return <p className="dc-empty">{EMPTY}</p>;
  return (
    <div className="dc-award-fit-list">
      {items.slice(0, 5).map((item: any, index: number) => {
        const confirmed = clean(item?.status) === "confirmed";
        const label = clean(item?.display_name) || clean(item?.name) || "Experiência avaliada";
        const weight = Number(item?.absolute_weight || 0);
        const canonical = fit?.__canonical;
        const itemCode = clean(
          item?.subfactor_code ??
            item?.criterion_code ??
            item?.code,
        ).toLowerCase();
        const itemLabel = normalizeCategory(label);
        let publishedWeight: number | null = null;
        let weightContext = "do fator";

        for (const factor of Array.isArray(canonical?.criteria?.factors)
          ? canonical.criteria.factors
          : []) {
          for (const sub of Array.isArray(factor?.subfactors)
            ? factor.subfactors
            : []) {
            const subCode = clean(sub?.code).toLowerCase();
            const subLabel = normalizeCategory(sub?.label);
            const sameCode = Boolean(
              itemCode && subCode && itemCode === subCode,
            );
            const sameLabel = Boolean(
              itemLabel &&
                subLabel &&
                (itemLabel === subLabel ||
                  itemLabel.includes(subLabel) ||
                  subLabel.includes(itemLabel)),
            );

            if (sameCode || sameLabel) {
              const candidate = Number(
                sub?.display_weight_percent ??
                  sub?.published_weight_percent ??
                  sub?.internal_weight_percent,
              );

              if (Number.isFinite(candidate)) {
                publishedWeight = candidate;
                weightContext = clean(sub?.weight_context) || "do fator";
              }
            }
          }
        }

        const requirementDetail = awardRequirementDetail(item, canonical);
        const statusLabel =
          clean(item?.status_label) ||
          (confirmed ? "Comprovado" : "Por demonstrar");

        return (
          <div className="dc-award-fit-row" key={`${label}-${index}`}>
            {confirmed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
            <div>
              <strong>{label}</strong>
              <span title={awardRequirementProvenance(item)}>
                {requirementDetail}
                {publishedWeight !== null
                  ? ` · ${publishedWeight}% ${weightContext}`
                  : weight
                    ? ` · ${weight}% da avaliação`
                    : ""}
                {statusLabel ? ` · ${statusLabel}` : ""}
              </span>
            </div>
          </div>
        );
      })}
      {Array.isArray(fit?.unrelated_project_typologies) && fit.unrelated_project_typologies.length ? (
        <p className="dc-award-fit-note">
          Projetos noutras tipologias ({fit.unrelated_project_typologies.slice(0, 4).join(", ")}) não contam para estes critérios.
        </p>
      ) : null}
    </div>
  );
}

function AiPanel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="dc-ai">
      <div className="dc-ai-heading">
        <Sparkles size={18} />
        <div>
          <span>Leitura AI</span>
          <h2>{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function TimelineSidebarCard({
  items,
}: {
  items: Fact[];
}) {
  const visibleItems = items.filter(
    (item) => item.confirmed && item.value !== EMPTY,
  );

  return (
    <article className="dc-side-timeline">
      <div className="dc-side-timeline-heading">
        <CalendarDays size={18} />
        <div>
          <span>Cronograma</span>
          <h3>Marcos do concurso</h3>
        </div>
      </div>

      {visibleItems.length ? (
        <div className="dc-side-timeline-list">
          {visibleItems.map((item) => (
            <div
              key={item.label}
              className={
                item.label === "Entrega das propostas"
                  ? "dc-side-timeline-item is-deadline"
                  : "dc-side-timeline-item"
              }
            >
              <i aria-hidden="true" />
              <div>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="dc-side-timeline-empty">
          Datas ainda por confirmar.
        </p>
      )}
    </article>
  );
}

export default function DesignCompetitionAnalysis({
  ficha,
  concurso,
  presentation,

  concursoId,}: Props) {
  const extraction = ficha?.design_competition_extraction || {};
  const procedureAnalysis = getProcedureAnalysis(ficha);
  const procedureCardAnalysis = buildProcedureCardAnalysis(
    ficha,
    procedureAnalysis,
  );
  const analysisFamily =
    clean(procedureAnalysis?.family) ||
    clean(ficha?.analysis_family) ||
    "design_competition";
  const isDesignCompetition = analysisFamily === "design_competition";
  const isProjectServices = analysisFamily === "project_services";
  const isDesignBuild = analysisFamily === "design_build";
  const interventionProgram =
    ficha?.intervention_program ||
    extraction?.intervention_program ||
    {};
  const isInterventionProgram = Boolean(
    ficha?.analysis_variant === "intervention_program" ||
      interventionProgram?.active,
  );
  const submissionRequirements =
    extraction?.submission_requirements ||
    ficha?.submission_requirements ||
    {};
  const program = isInterventionProgram
    ? interventionProgram
    : extraction?.functional_program ||
      extraction?.program_functional ||
      ficha?.functional_program ||
      ficha?.programa_funcional ||
      {};

  const title =
    clean(concurso?.titulo) ||
    clean(ficha?.identificacao?.titulo) ||
    clean(procedureAnalysis?.family_label) ||
    "Concurso de arquitetura";
  const entity =
    clean(concurso?.entidade) ||
    clean(ficha?.identificacao?.entidade);
  const location =
    clean(concurso?.localizacao) ||
    clean(ficha?.localizacao?.morada) ||
    clean(ficha?.identificacao?.localizacao);
  const procedure =
    clean(procedureAnalysis?.family_label) ||
    clean(ficha?.identificacao?.tipo_procedimento) ||
    clean(concurso?.tipo_procedimento) ||
    "Procedimento por confirmar";
  const officialUrl =
    clean(concurso?.link) ||
    clean(ficha?.identificacao?.link);

  const coverUrl =
    `/analises/${encodeURIComponent(String(concursoId))}-capa.png`;

  const procedureValue = getFact(extraction, "procedure_value");
  const constructionCost = getFact(
    extraction,
    "estimated_construction_cost",
  );
  const servicesValue = getFact(
    extraction,
    "design_services_value",
  );
  const financialEnrichment = extraction?.financial || {};
  const contractEnrichment = extraction?.contract || {};
  const servicesDisplay =
    clean(financialEnrichment?.design_services_value_display) ||
    servicesValue;
  const hasStructuredProgram = Boolean(program && Object.keys(program).length);
  const totalArea =
    clean(program?.area_intervencao?.value) ||
    clean(program?.total_area) ||
    (!hasStructuredProgram
      ? getFact(extraction, "area_intervencao") || getFact(extraction, "total_area")
      : "");
  const deadline =
    clean(concurso?.data_entrega_propostas) ||
    clean(concurso?.data_fim_calculada) ||
    clean(concurso?.data_limite) ||
    getFact(extraction, "submission_deadline");
  const criteriaFallback =
    clean(concurso?.criterio_resumo) ||
    clean(ficha?.criterios?.resumo) ||
    clean(concurso?.criterio_tipo) ||
    clean(ficha?.criterio_resumo) ||
    clean(ficha?.criterios?.criterio_adjudicacao);

  const criteria = buildCriteriaSummary(
    ficha,
    procedureAnalysis,
    criteriaFallback,
  );

  const documentStatus = documentStatusLabel(
    presentation?.document_status ||
      ficha?.document_insights?.document_status,
  );

  const procedureMetrics: any[] = Array.isArray(
    procedureAnalysis?.top_metrics,
  )
    ? procedureAnalysis.top_metrics
    : [];
  const procedureValueMetric = procedureMetrics.find(
    (item: any) => clean(item?.key) === "procedure_value",
  );
  const constructionMetric = procedureMetrics.find(
    (item: any) => clean(item?.key) === "construction_cost",
  );
  const procedureValueDisplay =
    clean(procedureValueMetric?.value) || procedureValue;
  const constructionCostDisplay =
    clean(constructionMetric?.value) || constructionCost;
  const constructionCostStatus =
    clean(constructionMetric?.status_label) || undefined;
  const metrics: Fact[] = procedureMetrics.length
    ? procedureMetrics.map((item: any): Fact => {
        const label = clean(item?.label) || "Indicador";
        const value =
          label === "Estado da documentação"
            ? documentStatusLabel(item?.value)
            : item?.value;
        return makeFact(
          label,
          value,
          120,
          clean(item?.status_label) || undefined,
        );
      })
    : [
        makeFact("Valor do procedimento", procedureValue, 90),
        makeFact(
      "Estimativa de custo da obra",
      constructionCostDisplay,
      90,
      constructionCostStatus,
    ),
        makeFact("Honorários de projeto", servicesDisplay, 90),
        makeFact("Área de intervenção", totalArea, 90),
        makeFact("Entrega das propostas", deadline, 105),
        makeFact("Critérios de adjudicação", criteria, 120),
        makeFact("Tipo de procedimento", procedure, 100),
        makeFact("Estado da documentação", documentStatus, 90),
      ];

  const prizeKeys = [
    "competition_prize_first",
    "competition_prize_second",
    "competition_prize_third",
    "competition_prize_mentions",
    "competition_prize_total",
  ];
  const prizes = prizeKeys
    .map((key) =>
      makeFact(LABELS[key], getFact(extraction, key), 90),
    )
    .filter((item) => item.confirmed);

  const financial = [
    ...(isDesignCompetition
      ? prizes.length
        ? prizes
        : [makeFact("Prémios do concurso", "", 90)]
      : []),
    makeFact(
      isDesignBuild
        ? "Preço base projeto + obra"
        : isProjectServices
          ? "Preço base dos serviços"
          : "Valor do procedimento",
      procedureValueDisplay,
      100,
    ),
    ...(servicesDisplay && clean(servicesDisplay) !== clean(procedureValueDisplay)
      ? [makeFact("Honorários de projeto", servicesDisplay, 90)]
      : []),
    makeFact(
      "Estimativa de custo da obra",
      constructionCostDisplay,
      110,
      constructionCostStatus,
    ),
    makeFact("Critérios de adjudicação", criteria, 140),
  ];

  const contractKeys = [
    "project_phases",
    "execution_project",
    "technical_assistance",
    "measurements",
    "quantity_schedule",
    "final_drawings",
    "specialties",
    "approval_requirement",
    "payment_conditions",
  ];
  const contract = [
    makeFact(
      "Fases do projeto",
      contractEnrichment?.phase_count
        ? `${contractEnrichment.phase_count} fases`
        : getFact(extraction, "project_phases"),
      90,
    ),
    makeFact(
      "Projeto de execução",
      getFact(extraction, "execution_project"),
      105,
    ),
    makeFact(
      "Assistência técnica",
      getFact(extraction, "technical_assistance"),
      105,
    ),
    makeFact(
      "Telas finais",
      getFact(extraction, "final_drawings"),
      90,
    ),
    makeFact(
      "Especialidades",
      contractEnrichment?.specialty_count
        ? `${contractEnrichment.specialty_count} especialidades`
        : getFact(extraction, "specialties"),
      90,
    ),
    makeFact(
      "Condições de pagamento",
      clean(contractEnrichment?.payment_summary) ||
        getFact(extraction, "payment_conditions"),
      100,
    ),
  ];


  const matching =
    ficha?.company_matching ||
    ficha?.adequacao_empresa ||
    {};
  const decision = ficha?.decisao || {};
  const awardFit =
    matching?.award_criteria_fit ??
    ficha?.adequacao_empresa?.award_criteria_fit ??
    {};
  const officialScore = buildOfficialScore(ficha, awardFit);
  const recommendation =
    compact(
      officialScore.recommendation ||
        (matching?.recommendation?.explanation ??
          matching?.final_recommendation?.explanation ??
          ficha?.recomendacao_final?.justificacao ??
          ficha?.decision_summary),
      260,
    ) || EMPTY;
  const awardFitActive = Boolean(awardFit?.active);
  const opportunities = enrichOpportunityCounts(
    listValues(
      matching?.oportunidades ??
        ficha?.adequacao_empresa?.oportunidades ??
        decision?.oportunidades,
      5,
    ),
    ficha,
  );
  const strengths = listValues(
    matching?.strengths ??
      ficha?.adequacao_empresa?.compatibility_explanation?.positive_factors,
    5,
  );
  const weaknesses = listValues(
    matching?.weaknesses ??
      ficha?.adequacao_empresa?.riscos_identificados ??
      ficha?.adequacao_empresa?.lacunas,
    5,
  );

  const areas: Fact[] = Array.isArray(program?.areas)
    ? program.areas
        .slice(0, 12)
        .map((item: any) =>
          makeFact(
            clean(item?.label) || "Área",
            clean(item?.value),
            85,
          ),
        )
    : [];

  const spaces = unique(program?.main_spaces || [], 10);
  const requirements = unique(program?.requirements || [], 8);
  const constraints = unique(program?.constraints || [], 8);
  const summary = compact(program?.summary, 620) || EMPTY;

  const extractedTimeline = Array.isArray(procedureAnalysis?.timeline)
    ? procedureAnalysis.timeline
    : [];
  const timeline = extractedTimeline.length
    ? extractedTimeline.map((item: any) =>
        makeFact(clean(item?.label) || "Marco", item?.value, 120),
      )
    : [
        makeFact(
          "Publicação do anúncio",
          clean(concurso?.data_publicacao_iso) ||
            clean(concurso?.data) ||
            clean(ficha?.identificacao?.data_publicacao) ||
            clean(ficha?.identificacao?.data),
          90,
        ),
        makeFact(
          "Pedidos de esclarecimento",
          getFact(extraction, "clarification_deadline"),
          120,
        ),
        makeFact(
          "Visita ao local",
          getFact(extraction, "site_visit"),
          120,
        ),
        makeFact("Entrega das propostas", deadline, 100),
      ];

  return (
    <main className="site-container dc-page">
      <AnalysisQuestionsModal ficha={ficha} concursoId={concursoId} />
      <header className="dc-hero">
        <a className="dc-back" href="/analise">
          <ArrowLeft size={15} />
          Voltar às análises
        </a>

        <div className="dc-hero-grid">
          <div>
            <span className="dc-kicker">
              {isDesignBuild
                ? "Análise de Conceção-Construção"
                : isProjectServices
                  ? "Análise de prestação de serviços de projeto"
                  : isInterventionProgram
                    ? "Análise de projeto e intervenção"
                    : "Análise de concurso de conceção"}
            </span>
            <h1>{title}</h1>
            <div className="dc-meta">
              {location ? (
                <span><MapPin size={15} />{location}</span>
              ) : null}
              {entity ? (
                <span><Building2 size={15} />{entity}</span>
              ) : null}
              <span><ClipboardCheck size={15} />{procedure}</span>
            </div>
          </div>

          <div className="dc-hero-media">
            <img
              src={coverUrl}
              alt=""
              onError={(event) => {
                const image = event.currentTarget;
                const wrapper = image.parentElement;
                image.remove();
                if (wrapper && !officialUrl) {
                  wrapper.style.display = "none";
                }
              }}
            />

            {officialUrl ? (
              <a
                className="dc-official"
                href={officialUrl}
                target="_blank"
                rel="noreferrer"
              >
                Ver concurso no portal
                <ExternalLink size={15} />
              </a>
            ) : null}
          </div>
        </div>
      </header>

      <section className="dc-metrics">
        {metrics.map((item: Fact) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small className={item.confirmed ? "ok" : "pending"}>
              {item.statusLabel ||
                (item.confirmed ? "Confirmado" : "Por confirmar")}
            </small>
          </article>
        ))}
      </section>

      <div className="dc-layout">
        <div className="dc-main">
          <AiPanel title="Vale a pena concorrer?">
            <div className="dc-decision">
              <div className="dc-score">
                <span>{officialScore.label}</span>
                <strong>{officialScore.displayValue}</strong>
                {officialScore.suffix ? <small>{officialScore.suffix}</small> : null}
                {officialScore.note ? <em>{officialScore.note}</em> : null}
              </div>

              <div className="dc-ai-copy">
                <span>Recomendação</span>
                <h3>{recommendation}</h3>
                <div className="dc-indicators">
                  <div>
                    <span>Elegibilidade</span>
                    <strong>
                      {clean(decision?.elegibilidade?.estado) || EMPTY}
                    </strong>
                  </div>
                  <div>
                    <span>Risco</span>
                    <strong>
                      {clean(decision?.risco?.nivel) || EMPTY}
                    </strong>
                  </div>
                  <div>
                    <span>Confiança</span>
                    <strong>
                      {clean(matching?.confidence?.level) ||
                        clean(matching?.confidence) ||
                        EMPTY}
                    </strong>
                  </div>
                </div>
              </div>

              <div className="dc-ai-copy">
                <span>{awardFitActive ? "Experiência que decide a nota" : "O que decide a nota"}</span>
                {awardFitActive ? (
                  <AwardFitList fit={{ ...awardFit, __canonical: ficha?.analysis_canonical }} />
                ) : (
                  <UniversalDecisionCriteria
                    ficha={ficha}
                    procedureAnalysis={procedureAnalysis}
                    criteriaSummary={criteria}
                    fallbackItems={opportunities}
                  />
                )}
              </div>
            </div>
          </AiPanel>

          <section>
            <div className="dc-heading">
              <span>Informação confirmada</span>
              <h2>Leitura estruturada das peças</h2>
            </div>

            <div className="dc-four">
              <article className="dc-card">
                <div className="dc-card-title">
                  <Trophy size={18} />
                  <h3>
                    {isInterventionProgram
                      ? "Preço e critérios"
                      : "Valores financeiros"}
                  </h3>
                </div>
                <FactRows items={financial} />
              </article>

              <UniversalSubmissionCards
                ficha={ficha}
                procedureAnalysis={procedureAnalysis}
              />

              {isDesignCompetition ? (
              <article className="dc-card">
                <div className="dc-card-title">
                  <Layers3 size={18} />
                  <h3>
                    {isInterventionProgram
                      ? "Equipa, fases e especialidades"
                      : "Contrato e pós-adjudicação"}
                  </h3>
                </div>
                <FactRows items={contract} />
                <DomainDetailsButton
                  label={
                    isInterventionProgram
                      ? "Ver equipa, fases e especialidades"
                      : "Ver obrigações contratuais completas"
                  }
                  title={
                    isInterventionProgram
                      ? "Equipa, fases e especialidades"
                      : "Contrato e pós-adjudicação"
                  }
                  sections={[
                    {
                      title: "Fases do projeto",
                      items: [
                        {
                          label: "Fases",
                          value: Array.isArray(
                            contractEnrichment?.phases,
                          )
                            ? contractEnrichment.phases.join(" · ")
                            : EMPTY,
                        },
                      ],
                    },
                    {
                      title: "Especialidades",
                      items: [
                        {
                          label: "Equipa técnica",
                          value: Array.isArray(
                            contractEnrichment?.specialties,
                          )
                            ? contractEnrichment.specialties.join(" · ")
                            : EMPTY,
                        },
                      ],
                    },
                    {
                      title: "Pagamento e entregáveis",
                      items: [
                        {
                          label: "Condições de pagamento",
                          value: Array.isArray(
                            contractEnrichment?.payment_conditions,
                          )
                            ? contractEnrichment.payment_conditions.join(" · ")
                            : EMPTY,
                        },
                        {
                          label: "Projeto de execução",
                          value:
                            getFact(extraction, "execution_project") ||
                            EMPTY,
                        },
                        {
                          label: "Assistência técnica",
                          value:
                            getFact(extraction, "technical_assistance") ||
                            EMPTY,
                        },
                        {
                          label: "Telas finais",
                          value:
                            getFact(extraction, "final_drawings") ||
                            EMPTY,
                        },
                        {
                          label: "Mapa de medições",
                          value:
                            getFact(extraction, "measurements") ||
                            EMPTY,
                        },
                        {
                          label: "Mapa de quantidades",
                          value:
                            getFact(extraction, "quantity_schedule") ||
                            EMPTY,
                        },
                      ],
                    },
                  ]}
                />
              </article>
              ) : null}


            </div>
          </section>

          <ProcedureSpecificCards analysis={procedureAnalysis} ficha={ficha} />

          <section className="dc-program">
            <div className="dc-heading">
              <span>
                {isProjectServices || isDesignBuild || isInterventionProgram
                  ? "Programa de intervenção"
                  : "Programa funcional"}
              </span>
              <h2>
                {isProjectServices || isDesignBuild || isInterventionProgram
                  ? "Síntese territorial e técnica"
                  : "Resumo do programa preliminar"}
              </h2>
            </div>

            {isInterventionProgram || isProjectServices || isDesignBuild ? (
              <InterventionProgramSummaryCard
                program={interventionProgram}
              />
            ) : (
              <FunctionalProgramSummaryCard
                functionalProgram={program}
                extraction={extraction}
              />
            )}
          </section>


          <div className="dc-bottom dc-bottom-single">
            <article className="dc-card">
              <div className="dc-card-title">
                <FileText size={18} />
                <h3>Origem da extração</h3>
              </div>
              <p className="dc-source-note">
                Os cartões brancos mostram informação extraída das peças.
                Os blocos amarelos mostram interpretação AI.
              </p>
              <div className="dc-counts">
                <span>{extraction?.counts?.facts ?? 0} factos</span>
                <span>
                  {isInterventionProgram
                    ? `${interventionProgram?.counts?.confirmed_themes ?? 0} temas confirmados`
                    : `${extraction?.counts?.areas ?? 0} áreas`}
                </span>
                <span>
                  {isInterventionProgram
                    ? `${interventionProgram?.counts?.source_documents ?? 0} fontes`
                    : `${extraction?.counts?.spaces ?? 0} espaços`}
                </span>
              </div>
            </article>

          </div>
        </div>

        <aside className="dc-sidebar">
          <TimelineSidebarCard items={timeline} />
          <ProjectInfoPanel ficha={ficha} />
        </aside>
      </div>

      <style jsx global>{`
        .site-container.dc-page {
          max-width: 1500px;
          padding-bottom: 56px;
          color: #181a16;
        }

        .dc-hero {
          padding: 26px 0 22px;
        }

        .dc-back {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          margin-bottom: 18px;
          color: #4d524b;
          font-size: 13px;
          text-decoration: none;
        }

        .dc-hero-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(250px, 330px);
          gap: 34px;
          align-items: start;
        }

        .dc-kicker,
        .dc-heading span,
        .dc-ai-heading span {
          color: #6d8044;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .dc-hero h1 {
          max-width: 860px;
          margin: 8px 0 14px;
          font-size: clamp(26px, 2.35vw, 38px);
          line-height: 1.08;
          letter-spacing: -0.032em;
        }

        .dc-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 18px;
          color: #656a62;
          font-size: 13px;
        }

        .dc-meta span {
          display: inline-flex;
          align-items: center;
          gap: 7px;
        }

        .dc-hero-media {
          display: grid;
          gap: 10px;
          width: 100%;
        }

        .dc-hero-media img {
          display: block;
          width: 100%;
          aspect-ratio: 4 / 3;
          border-radius: 14px;
          object-fit: cover;
          background: #eef0ea;
        }

        .dc-official {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 9px;
          width: 100%;
          padding: 13px 18px;
          border-radius: 9px;
          background: #587436;
          color: white;
          font-weight: 700;
          text-decoration: none;
        }

        .dc-metrics {
          display: grid;
          grid-template-columns: repeat(8, minmax(0, 1fr));
          gap: 10px;
          margin-bottom: 22px;
        }

        .dc-metrics article {
          min-height: 128px;
          display: flex;
          flex-direction: column;
          gap: 9px;
          padding: 15px;
          border: 1px solid #e2e3dd;
          border-radius: 14px;
          background: #fff;
          min-width: 0;
        }

        .dc-metrics article > span {
          color: #6d716a;
          font-size: 11px;
        }

        .dc-metrics article > strong {
          font-size: 16px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }

        .dc-metrics article > small {
          width: fit-content;
          margin-top: auto;
          padding: 4px 7px;
          border-radius: 999px;
          font-size: 10px;
        }

        .dc-metrics small.ok {
          background: #e6eee0;
          color: #486039;
        }

        .dc-metrics small.pending {
          background: #fff0c8;
          color: #835d0a;
        }

        .dc-layout {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 320px;
          gap: 22px;
          align-items: start;
        }

        .dc-main {
          display: grid;
          gap: 25px;
          min-width: 0;
        }

        .dc-sidebar {
          position: sticky;
          top: 84px;
        }

        .dc-sidebar {
          display: grid;
          gap: 10px;
        }

        .dc-side-timeline {
          padding: 18px;
          border: 1px solid #dfe4d8;
          border-radius: 15px;
          background: #ffffff;
        }

        .dc-side-timeline-heading {
          display: flex;
          align-items: center;
          gap: 10px;
          padding-bottom: 14px;
          border-bottom: 1px solid #e7eae3;
        }

        .dc-side-timeline-heading > svg {
          color: #607b3f;
        }

        .dc-side-timeline-heading span {
          display: block;
          color: #6d8044;
          font-size: 9px;
          font-weight: 800;
          letter-spacing: 0.13em;
          text-transform: uppercase;
        }

        .dc-side-timeline-heading h3 {
          margin: 3px 0 0;
          font-size: 15px;
        }

        .dc-side-timeline-list {
          display: grid;
          margin-top: 15px;
        }

        .dc-side-timeline-item {
          position: relative;
          display: grid;
          grid-template-columns: 14px 1fr;
          gap: 9px;
          min-height: 55px;
        }

        .dc-side-timeline-item:not(:last-child)::after {
          content: "";
          position: absolute;
          top: 13px;
          bottom: -2px;
          left: 5px;
          width: 1px;
          background: #dce3d4;
        }

        .dc-side-timeline-item i {
          position: relative;
          z-index: 1;
          width: 11px;
          height: 11px;
          margin-top: 2px;
          border: 2px solid #718a4c;
          border-radius: 999px;
          background: #ffffff;
        }

        .dc-side-timeline-item.is-deadline i {
          border-color: #587436;
          background: #587436;
        }

        .dc-side-timeline-item span {
          display: block;
          color: #73786f;
          font-size: 10px;
        }

        .dc-side-timeline-item strong {
          display: block;
          margin-top: 4px;
          font-size: 12px;
          line-height: 1.35;
        }

        .dc-side-timeline-item.is-deadline strong {
          color: #4e6b31;
        }

        .dc-side-timeline-empty {
          margin: 14px 0 0;
          color: #73786f;
          font-size: 12px;
        }

        .dc-bottom-single {
          grid-template-columns: 1fr;
        }

        .dc-ai {
          padding: 23px;
          border: 1px solid #ead89b;
          border-radius: 17px;
          background: #fff5cd;
        }

        .dc-ai-heading,
        .dc-card-title {
          display: flex;
          align-items: center;
          gap: 9px;
        }

        .dc-ai-heading h2,
        .dc-card-title h3,
        .dc-heading h2 {
          margin: 3px 0 0;
        }

        .dc-decision {
          display: grid;
          grid-template-columns: 150px 1.15fr 1fr;
          gap: 24px;
          margin-top: 20px;
        }

        .dc-company {
          display: grid;
          grid-template-columns: 150px repeat(3, minmax(0, 1fr));
          gap: 22px;
          margin-top: 20px;
        }

        .dc-score {
          width: 142px;
          aspect-ratio: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          border: 7px solid #738b48;
          border-right-color: #e4d9b4;
          border-radius: 999px;
          background: #fffdf4;
        }

        .dc-score span {
          color: #676c63;
          font-size: 11px;
        }

        .dc-score strong {
          margin-top: 7px;
          font-size: 42px;
          line-height: 1;
        }

        .dc-ai-copy > span {
          color: #68745c;
          font-size: 11px;
          font-weight: 700;
        }

        .dc-ai-copy h3 {
          margin: 7px 0 10px;
          font-size: 18px;
          line-height: 1.35;
        }

        .dc-ai-copy p {
          margin: 8px 0 0;
          line-height: 1.55;
        }

        .dc-indicators {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin-top: 18px;
        }

        .dc-indicators div {
          padding-top: 10px;
          border-top: 1px solid #e2d39d;
        }

        .dc-indicators span {
          display: block;
          margin-bottom: 5px;
          color: #777b72;
          font-size: 10px;
        }

        .dc-heading {
          margin-bottom: 13px;
        }

        .dc-heading h2 {
          font-size: 22px;
        }

        .dc-four,
        .dc-program-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
        }

        .dc-card,
        .dc-summary {
          min-width: 0;
          padding: 18px;
          border: 1px solid #e1e2dd;
          border-radius: 15px;
          background: #fff;
        }

        .dc-card h3 {
          margin: 0;
          font-size: 14px;
        }

        .dc-rows {
          margin-top: 13px;
        }

        .dc-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          padding: 9px 0;
          border-bottom: 1px solid #ecece7;
        }

        .dc-row:last-child {
          border-bottom: 0;
        }

        .dc-row span {
          color: #686d66;
          font-size: 11px;
        }

        .dc-row strong {
          max-width: 160px;
          text-align: right;
          font-size: 11px;
          line-height: 1.35;
          overflow-wrap: anywhere;
        }

        .dc-program {
          display: grid;
          gap: 11px;
        }

        .dc-summary > span {
          color: #6b7069;
          font-size: 11px;
          font-weight: 700;
        }

        .dc-summary p {
          max-width: 1100px;
          margin: 10px 0 0;
          line-height: 1.58;
        }

        .dc-list {
          list-style: none;
          padding: 0;
          margin: 11px 0 0;
          display: grid;
          gap: 9px;
        }

        .dc-list li {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          font-size: 12px;
          line-height: 1.42;
        }

        .dc-list svg {
          flex: 0 0 auto;
          margin-top: 2px;
          color: #688453;
        }

        .dc-list.warning svg {
          color: #aa7420;
        }

        .dc-empty {
          color: #858981;
          font-size: 12px;
        }

        .dc-bottom {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }

        .dc-source-note {
          color: #656a62;
          line-height: 1.5;
        }

        .dc-counts {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 15px;
        }

        .dc-counts span {
          padding: 5px 8px;
          border-radius: 999px;
          background: #edf1e7;
          color: #536540;
          font-size: 10px;
        }

        @media (max-width: 1280px) {
          .dc-metrics {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }

          .dc-four,
          .dc-program-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .dc-company {
            grid-template-columns: 150px 1fr 1fr;
          }
        }

        @media (max-width: 980px) {
          .dc-layout,
          .dc-hero-grid,
          .dc-decision,
          .dc-company {
            grid-template-columns: 1fr;
          }

          .dc-sidebar {
            position: static;
          }
        }

        @media (max-width: 680px) {
          .dc-metrics,
          .dc-four,
          .dc-program-grid,
          .dc-bottom {
            grid-template-columns: 1fr;
          }

          .dc-score {
            width: 100%;
            aspect-ratio: auto;
            border-radius: 15px;
            padding: 20px;
          }

          .dc-indicators {
            grid-template-columns: 1fr;
          }
        }

        .dc-score em {
          display: block;
          max-width: 150px;
          margin-top: 8px;
          color: #6c6f67;
          font-size: 10px;
          font-style: normal;
          line-height: 1.35;
        }
        .dc-award-fit-list {
          display: grid;
          gap: 9px;
          margin-top: 10px;
        }
        .dc-award-fit-row {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr);
          gap: 8px;
          align-items: start;
        }
        .dc-award-fit-row svg {
          margin-top: 2px;
        }
        .dc-award-fit-row div {
          min-width: 0;
        }
        .dc-award-fit-row strong,
        .dc-award-fit-row span {
          display: block;
          white-space: normal;
          overflow-wrap: anywhere;
        }
        .dc-award-fit-row strong {
          font-size: 12px;
        }
        .dc-award-fit-row span {
          margin-top: 2px;
          color: #6c6f67;
          font-size: 10px;
          line-height: 1.35;
        }
        .dc-award-fit-note {
          margin: 4px 0 0;
          padding-top: 8px;
          border-top: 1px solid rgba(82, 91, 67, 0.18);
          color: #6c6f67;
          font-size: 10px;
          line-height: 1.4;
        }
      `}</style>
    </main>
  );
}
