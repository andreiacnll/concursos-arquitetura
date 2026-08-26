"use client";

// CNLL_DIRECT_FICHA_CARDS_V17_10

// CNLL_CARDS_MODAL_V17_9B

// CNLL_UNIVERSAL_CARD_SOURCE_V17_7
// CNLL_UNIVERSAL_MERGE_V17_8

import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
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
  UsersRound,
} from "lucide-react";

import FunctionalProgramSummaryCard from "@/components/analise/FunctionalProgramSummaryCard";
import InterventionProgramSummaryCard from "@/components/analise/InterventionProgramSummaryCard";

import UniversalDecisionCriteria from "@/components/analise/UniversalDecisionCriteria";

import AnalysisQuestionsModal from "@/components/analise/AnalysisQuestionsModal";

import { buildCriteriaSummary, buildProcedureCardAnalysis, buildUniversalContract, buildUniversalSubmission, getProcedureAnalysis } from "@/lib/analysis-universal";
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

function presentationItemText(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const item = value as Record<string, unknown>;
    return clean(
      item.title ??
        item.value ??
        item.normalized_value ??
        item.text ??
        item.label ??
        item.name ??
        item.description ??
        "",
    );
  }
  return clean(value);
}

function uniquePresentationItems(values: unknown[], limit: number): string[] {
  const seen = new Set<string>();
  return values
    .map(presentationItemText)
    .filter((item) => {
      const key = normalizeCategory(item);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, limit);
}

function isSafeExtractedSubmissionDeadline(value: unknown): boolean {
  const text = clean(value);
  const normalized = normalizeCategory(text);
  if (!text) return false;
  return !/(habilit|execucao|esclarec|visita|garantia|resposta|contrato)/.test(normalized);
}
function collectionItems(value: unknown): any[] {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined);
  if (value && typeof value === "object") {
    const item = value as Record<string, unknown>;
    if (Array.isArray(item.items)) return item.items.filter(Boolean);
    return [value];
  }
  return value === null || value === undefined || value === "" ? [] : [value];
}

function uniquePresentationRecords(values: unknown[], limit = 24): any[] {
  const seen = new Set<string>();
  const records: any[] = [];
  for (const value of values) {
    for (const item of collectionItems(value)) {
      const label = presentationItemText(item);
      const key = normalizeCategory(label);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      records.push(item);
      if (records.length >= limit) return records;
    }
  }
  return records;
}

function withoutPresentationDuplicates(items: any[], excluded: any[]): any[] {
  const excludedLabels = new Set(
    excluded.map(presentationItemText).map(normalizeCategory).filter(Boolean),
  );
  return items.filter((item) => !excludedLabels.has(normalizeCategory(presentationItemText(item))));
}
function presentationItemDetail(value: any): string {
  if (!value || typeof value !== "object") return "";
  return compact(
    value.description ??
      value.summary ??
      value.detail ??
      value.required?.text ??
      value.requirement_text ??
      value.condition ??
      value.source_excerpt ??
      value.evidence_excerpt ??
      "",
    150,
  );
}

function presentationItemBadges(value: any): string[] {
  if (!value || typeof value !== "object") return [];
  const count = clean(value.quantity ?? value.count);
  const pages = clean(value.maximum_pages ?? value.max_pages);
  const size = clean(value.maximum_size_mb ?? value.max_file_size ?? value.max_size_mb);
  return uniquePresentationItems([
    value.format,
    value.file_format,
    value.formats,
    value.page_size,
    value.orientation,
    value.delivery_mode,
    count ? `${count} unidades` : "",
    pages ? `max. ${pages} paginas` : "",
    size ? `max. ${size} MB` : "",
  ], 7);
}

type DeliveryPreview = {
  label: string;
  summary: string;
};

function deliveryLabel(value: any): string {
  const label = clean(
    value?.title ??
      value?.name ??
      value?.label ??
      value?.description ??
      value?.key,
  );
  return compact(label.replace(/\s*[—–-]\s*(?:PDF|JPG|PNG|XLS|DWG)\b.*$/i, ""), 54);
}

function deliverySummary(value: any): string {
  const quantity = clean(value?.quantity ?? value?.count ?? value?.number_of_files);
  const format = clean(value?.format ?? value?.file_format ?? value?.file_type);
  const pageSize = clean(value?.page_size ?? value?.dimension ?? value?.dimensions);
  const orientation = clean(value?.orientation);
  const pages = clean(value?.maximum_pages ?? value?.max_pages ?? value?.recommended_pages);
  const size = clean(value?.maximum_size_mb ?? value?.max_file_size ?? value?.max_size_mb);
  const quantityNumber = numericValue(quantity);
  const parts: string[] = [];

  if (quantityNumber !== null && quantityNumber > 1) {
    parts.push(`${quantity} x ${format || pageSize || "unidades"}`);
  } else if (format) {
    parts.push(format);
  } else if (pageSize) {
    parts.push(pageSize);
  }
  if (format && pageSize) parts.push(pageSize);
  if (orientation) parts.push(orientation);
  if (pages) parts.push(`≤${pages} pág.`);
  if (size) parts.push(`≤${size} MB`);

  return parts.join(" · ");
}

function buildDeliveryPreviews(submission: any): { items: DeliveryPreview[]; total: number } {
  const proposalItems = Array.isArray(submission?.proposalDocuments)
    ? submission.proposalDocuments
    : [];
  const fallbackItems = Array.isArray(submission?.formatsAndLimits)
    ? submission.formatsAndLimits
    : [];
  const sourceItems = proposalItems.length ? proposalItems : fallbackItems;
  const seen = new Set<string>();
  const items = sourceItems
    .filter((item: any) => {
      const category = normalizeCategory(`${item?.category} ${item?.effect} ${item?.group}`);
      return !/(administrative|submission rule|formal risk|post selection|habilit)/.test(category);
    })
    .map((item: any) => ({
      label: deliveryLabel(item),
      summary: deliverySummary(item),
      priority: normalizeCategory(`${deliveryLabel(item)} ${item?.category}`),
    }))
    .filter((entry: any) => {
      const key = normalizeCategory(entry.label);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((left: any, right: any) => {
      const rank = (value: string) =>
        /painel|peca grafica|desenh/.test(value) ? 1 :
        /caderno|memoria|relatorio/.test(value) ? 2 :
        /imagem|render/.test(value) ? 3 :
        /area/.test(value) ? 4 :
        /estimativa|orcamento|quantidade/.test(value) ? 5 :
        /digital|reproduc|ficheiro/.test(value) ? 6 : 7;
      return rank(left.priority) - rank(right.priority);
    })
    .map((entry: any) => ({ label: entry.label, summary: entry.summary }));

  return { items, total: items.length };
}
function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = clean(value);
  if (!text || !/^\d+(?:[.,]\d+)?$/.test(text)) return null;
  const parsed = Number(text.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = numericValue(value);
    if (parsed !== null) return parsed;
  }
  return null;
}

function sourceDocumentLabel(item: any): string {
  if (!item || typeof item !== "object") return presentationItemText(item);
  const source = item.source ?? {};
  return clean(
    item.source_heading ??
      item.document_title ??
      item.display_name ??
      source.section ??
      source.document ??
      item.source_document ??
      item.file_name ??
      item.filename ??
      item.title ??
      "",
  );
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

  const officialTitle =
    clean(concurso?.titulo) ||
    clean(ficha?.identificacao?.titulo);
  const summarizedTitle = clean(concurso?.titulo_resumido);
  const title =
    summarizedTitle ||
    officialTitle ||
    clean(procedureAnalysis?.family_label) ||
    "Concurso de arquitetura";
  const titleUsesOfficialFallback = !summarizedTitle && Boolean(officialTitle);
  const entity =
    clean(concurso?.entidade) ||
    clean(ficha?.identificacao?.entidade);
  const location =
    clean(concurso?.municipio) ||
    clean(ficha?.localizacao?.municipio) ||
    clean(concurso?.localizacao) ||
    clean(ficha?.identificacao?.localizacao);
  const locationAddress =
    clean(concurso?.morada) ||
    clean(ficha?.localizacao?.morada);
  const mapQuery = [
    clean(concurso?.latitude) && clean(concurso?.longitude)
      ? `${clean(concurso.latitude)},${clean(concurso.longitude)}`
      : "",
    locationAddress,
    location,
  ].find(Boolean) || "";
  const mapUrl = mapQuery
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery)}`
    : "";
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
  const extractedSubmissionDeadline = getFact(extraction, "submission_deadline");
  const deadline =
    clean(concurso?.data_entrega_propostas) ||
    (isSafeExtractedSubmissionDeadline(extractedSubmissionDeadline)
      ? extractedSubmissionDeadline
      : "");
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

  const submission = buildUniversalSubmission(ficha, procedureAnalysis);
  const decisionRequirements = Array.isArray(ficha?.analysis_canonical?.requirements)
    ? ficha.analysis_canonical.requirements
    : [];
  const hasCanonicalRequirementStates = decisionRequirements.some((item: any) =>
    Boolean(clean(item?.result ?? item?.profile ?? item?.status)),
  );
  const requirementCounts = decisionRequirements.reduce((counts: { met: number; pending: number; blocked: number }, item: any) => {
    const status = resultStatus(item?.result ?? item?.profile);
    if (status.includes("not met") || status.includes("nao cumpre") || status.includes("failed")) counts.blocked += 1;
    else if (status.includes("met") || status.includes("cumpre") || status.includes("confirmed") || status.includes("confirmado")) counts.met += 1;
    else counts.pending += 1;
    return counts;
  }, { met: 0, pending: 0, blocked: 0 });
  const decisionTitle = !hasCanonicalRequirementStates
    ? "Requisitos ainda não classificados."
    : requirementCounts.blocked
      ? "Existem requisitos impeditivos."
      : requirementCounts.pending
        ? "Há requisitos a confirmar."
        : requirementCounts.met
          ? "Requisitos avaliados sem impeditivos."
          : "Decisão por confirmar.";
  const deliveryItems = buildDeliveryPreviews(submission);
  const legacyTeam = ficha?.equipa || {};
  const teamItems = uniquePresentationItems([
    ...(Array.isArray(procedureCardAnalysis?.technical_team) ? procedureCardAnalysis.technical_team : []),
    ...decisionRequirements.filter((item: any) => ["team", "evaluation"].includes(normalizeCategory(item?.nature))),
    ...(Array.isArray(legacyTeam?.equipa_minima) ? legacyTeam.equipa_minima : []),
    ...(Array.isArray(legacyTeam?.especialidades) ? legacyTeam.especialidades : []),
    ...(Array.isArray(legacyTeam?.consultores_obrigatorios) ? legacyTeam.consultores_obrigatorios : []),
    ...(Array.isArray(legacyTeam?.habilitacoes_exigidas) ? legacyTeam.habilitacoes_exigidas : []),
  ], 5);
  const universalContract = buildUniversalContract(ficha, procedureAnalysis);
  const technicalTeam = uniquePresentationRecords([
    procedureCardAnalysis?.technical_team,
    decisionRequirements.filter((item: any) => normalizeCategory(item?.nature) === "team"),
    legacyTeam?.equipa_minima,
  ]);
  const teamCoordination = uniquePresentationRecords([
    legacyTeam?.equipa_minima,
    technicalTeam.filter((item: any) => /coorden|responsavel|autor/.test(normalizeCategory(presentationItemText(item)))),
  ]);
  const teamSpecialties = uniquePresentationRecords([
    legacyTeam?.especialidades,
    universalContract?.specialties,
    technicalTeam.filter((item: any) => /arquitetura|estrutur|paisag|avac|acust|scie|eletric|hidraulic|instalac/.test(normalizeCategory(presentationItemText(item)))),
  ]);
  const teamConsultants = withoutPresentationDuplicates(uniquePresentationRecords([
    legacyTeam?.consultores_obrigatorios,
    technicalTeam.filter((item: any) => /consult|bim|acust|sustent/.test(normalizeCategory(presentationItemText(item)))),
  ]), [...teamCoordination, ...teamSpecialties]);
  const teamQualifications = withoutPresentationDuplicates(uniquePresentationRecords([
    legacyTeam?.habilitacoes_exigidas,
    technicalTeam.filter((item: any) => /habilit|inscri|certific|ordem|qualific/.test(normalizeCategory(`${presentationItemText(item)} ${presentationItemDetail(item)}`))),
  ]), [...teamCoordination, ...teamSpecialties, ...teamConsultants]);
  const teamExperience = withoutPresentationDuplicates(uniquePresentationRecords([
    decisionRequirements.filter((item: any) => {
      const text = normalizeCategory(`${presentationItemText(item)} ${presentationItemDetail(item)}`);
      return ["experiencia", "anos", "projeto", "obra concluida", "valor minimo", "tipologia"].some((term) => text.includes(term));
    }),
    technicalTeam.filter((item: any) => Boolean(item?.parameters?.years || item?.parameters?.project_value_eur)),
  ]), [...teamCoordination, ...teamSpecialties, ...teamConsultants, ...teamQualifications]);
  const contractPhases = uniquePresentationRecords([universalContract?.phases]);
  const contractPayments = uniquePresentationRecords([universalContract?.payments]);
  const contractObligations = uniquePresentationRecords([
    universalContract?.scope_services,
    universalContract?.deliverables,
  ]);
  const contractRisks = uniquePresentationRecords([universalContract?.risks]);
  const audit = ficha?.document_insights?.document_audit || extraction?.document_audit || ficha?.document_audit || {};
  const documentsProcessed = firstNumber(
    audit?.documents_processed,
    audit?.documents_found,
    extraction?.counts?.documents_processed,
    extraction?.counts?.documents,
  );
  const documentsRead = firstNumber(
    submission.documentsRead,
    audit?.documents_read,
    audit?.reader_accepted_documents,
  );
  const sourceDocuments = uniquePresentationRecords([
    submission.sourceDocuments,
    audit?.official_documents_found,
  ]);
  const analysisUpdatedAt = clean(
    presentation?.updated_at ||
      ficha?.updated_at ||
      ficha?.analysis_updated_at ||
      ficha?._integration?.submission_requirements?.saved_at_utc,
  );  const decisionFactors = [
    requirementCounts.blocked > 0 ? {
      priority: 1, level: "negative", title: "Elegibilidade e requisitos impeditivos",
      description: `${requirementCounts.blocked} requisito(s) impeditivo(s) ainda nao cumprido(s).`,
    } : null,
    weaknesses.length ? {
      priority: 2, level: "negative", title: "Fator de risco identificado",
      description: compact(weaknesses[0], 96),
    } : null,
    requirementCounts.pending > 0 ? {
      priority: 3, level: "warning", title: "Informacao ainda por confirmar",
      description: `${requirementCounts.pending} requisito(s) relevante(s) ainda precisa(m) de validacao.`,
    } : null,
    officialScore.active && officialScore.maximum !== null ? {
      priority: 4, level: "warning", title: "Experiencia e equipa influenciam a avaliacao",
      description: compact(officialScore.note, 96),
    } : null,
    strengths.length ? {
      priority: 5, level: "positive", title: "Alinhamento favoravel com a empresa",
      description: compact(strengths[0], 96),
    } : null,
    criteria && criteria !== EMPTY ? {
      priority: 6, level: "positive", title: "Criterios de adjudicacao relevantes",
      description: compact(criteria, 96),
    } : null,
  ].filter(Boolean).sort((left: any, right: any) => left.priority - right.priority).slice(0, 3) as Array<{
    level: "negative" | "warning" | "positive"; title: string; description: string;
  }>;
  const decisionCardTitle = !hasCanonicalRequirementStates
    ? "O que influencia a decisao"
    : requirementCounts.blocked
      ? "Porque nao recomendamos concorrer"
      : requirementCounts.pending
        ? "O que condiciona a decisao"
        : "Porque vale a pena";
  const timelineItems = timeline.filter((item) => item.confirmed && item.value !== EMPTY);
  const summaryEconomicMetric = servicesDisplay && clean(servicesDisplay) !== clean(procedureValueDisplay)
    ? ["Honorários", servicesDisplay]
    : constructionCostDisplay && clean(constructionCostDisplay) !== clean(procedureValueDisplay)
      ? ["Custo estimado", constructionCostDisplay]
      : ["Tipo de procedimento", procedure];
  const summaryMetrics = [
    ["Prazo de entrega", deadline || EMPTY],
    ["Valor base", procedureValueDisplay || constructionCostDisplay],
    summaryEconomicMetric,
    ["Critério de adjudicação", criteria],
    ["Prémios", prizes.length ? prizes.map((item) => item.value).join(" · ") : ""],
  ].filter(([, value]) => clean(value));
  return <main className="site-container dc-page analysis-redesign">
    <AnalysisQuestionsModal ficha={ficha} concursoId={concursoId} inlineTriggerLabel="Confirmar requisitos" />
    <header className="ar-header">
      <a href="/analise"><ArrowLeft size={16} />Voltar as analises</a>
      <div><h1 className={titleUsesOfficialFallback ? "ar-title-fallback" : undefined} title={officialTitle || undefined}>{title}</h1><p>{entity ? <span><Building2 size={15} />{entity}</span> : null}{procedure ? <span><ClipboardCheck size={15} />{procedure}</span> : null}{analysisFamily ? <span><Layers3 size={15} />{analysisFamily.replace(/_/g, " ")}</span> : null}{location ? <span><MapPin size={15} />{location}</span> : null}{locationAddress ? <span className="ar-address">{locationAddress}{mapUrl ? <a href={mapUrl} target="_blank" rel="noreferrer">Ver no mapa <b>→</b></a> : null}</span> : null}</p></div>
      {officialUrl ? <a className="ar-official" href={officialUrl} target="_blank" rel="noreferrer">Abrir fonte oficial <ExternalLink size={16} /></a> : null}
    </header>
    <section className="ar-decision">
      <div className="ar-decision-copy"><i className={requirementCounts.blocked ? "blocked" : requirementCounts.pending ? "pending" : ""}>{requirementCounts.blocked ? <AlertTriangle size={29} /> : <CheckCircle2 size={32} />}</i><div><small>Decisão AI</small><h2>{decisionTitle}</h2><p>{recommendation}</p></div></div>
      <div className="ar-counts">{hasCanonicalRequirementStates ? <><div className="met"><strong>{requirementCounts.met}</strong><span>Cumpridos</span></div><div className="pending"><strong>{requirementCounts.pending}</strong><span>A confirmar</span></div><div className="blocked"><strong>{requirementCounts.blocked}</strong><span>Impeditivos</span></div></> : <div className="ar-counts-neutral"><strong>Requisitos ainda nao classificados</strong><span>Existem requisitos estruturados, mas sem estados canónicos para os classificar.</span></div>}<a href="#requisitos">Ver requisitos</a></div>
    </section>
    {summaryMetrics.length ? <section className="ar-summary">{summaryMetrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</section> : null}
    <section className="ar-grid">
      <DeliverablesCard items={deliveryItems.items} total={deliveryItems.total} />
      <OverviewCard index="02" icon={<UsersRound size={18} />} title="Equipa e experiência" description="Requisitos profissionais identificados." items={teamItems} href="#equipa" action="Ver requisitos completos" empty="Equipa por confirmar." />
      <article className="ar-card"><CardTitle index="03" icon={<CalendarDays size={18} />} title="Calendário" description="Datas-chave do procedimento." /><div className="ar-card-content">{timelineItems.length ? <ol>{timelineItems.slice(0,4).map((item) => <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>)}</ol> : <em>Datas por confirmar.</em>}</div><CardCta href="#cronograma">Ver cronograma completo</CardCta></article>
      <ResolutionCard title={decisionCardTitle} items={decisionFactors} />
    </section>
    <section className="ar-details">
            <Detail id="explicacao" icon={<Target size={19} />} title="Explicação da decisão" text="Fatores que mais influenciam a decisão de concorrer.">
        <div className="ar-decision-explanation">
          {recommendation ? <p>{recommendation}</p> : null}
          <StructuredSection groups={[{ title: "Fatores determinantes", description: "Síntese baseada nos requisitos e evidência disponíveis.", items: decisionFactors }]} empty="Não existem fatores determinantes adicionais identificados." />
        </div>
      </Detail><Detail id="requisitos" icon={<ClipboardCheck size={19} />} title="Critérios de adjudicação" text="Fatores, subfatores, ponderações e metodologia de avaliação." open><UniversalDecisionCriteria ficha={ficha} procedureAnalysis={procedureAnalysis} criteriaSummary={criteria} fallbackItems={opportunities} /></Detail>
      <Detail id="programa" icon={<Layers3 size={19} />} title="Programa funcional e áreas" text="Descrição do programa, áreas e requisitos funcionais.">{isInterventionProgram || isProjectServices || isDesignBuild ? <InterventionProgramSummaryCard program={interventionProgram} /> : <FunctionalProgramSummaryCard functionalProgram={program} extraction={extraction} />}</Detail>
      <Detail id="submissao" icon={<FileText size={19} />} title="Entregas e submissão" text="O que entregar e como submeter a proposta."><StructuredSection summary={[`${submission.participantDocuments.length} documentos obrigatorios`, `${submission.proposalDocuments.length} elementos tecnicos`, `${submission.formatsAndLimits.length} regras de submissao`]} groups={[{ title: "Documentos da proposta", description: "Documentos administrativos e declarações exigidos.", items: submission.participantDocuments }, { title: "Conteúdo técnico", description: "Elementos técnicos e gráficos da proposta.", items: submission.proposalDocuments }, { title: "Formatos e regras", description: "Formatos, limites e regras de entrega.", items: submission.formatsAndLimits, badges: true }]} empty="Elementos de submissão ainda não identificados nas peças processadas." /></Detail>
      <Detail id="equipa" icon={<UsersRound size={19} />} title="Equipa e experiência" text="Quem precisamos de ter e o que demonstrar."><StructuredSection groups={[{ title: "Coordenacao", description: "Responsaveis e elementos nucleares da equipa.", items: technicalTeam }, { title: "Especialidades obrigatorias", description: "Especialidades tecnicas identificadas.", items: teamSpecialties }, { title: "Consultores e funcoes adicionais", description: "Funcoes complementares exigidas.", items: teamConsultants }, { title: "Habilitacoes e comprovacao", description: "Inscricoes, certificados e documentos profissionais.", items: teamQualifications }, { title: "Experiencia exigida", description: "Experiencia profissional e projetos valorizados.", items: teamExperience }]} empty="Requisitos de equipa e experiencia ainda nao identificados nas pecas processadas." /></Detail>
            <Detail id="cronograma" icon={<CalendarDays size={19} />} title="Calendário" text="Datas-chave do procedimento.">
        {timelineItems.length ? <ol className="ar-timeline-detail">{timelineItems.map((item) => <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>)}</ol> : <p className="ar-section-empty">Datas do procedimento ainda não identificadas nas peças processadas.</p>}
      </Detail>
      <Detail id="condicoes" icon={<ClipboardCheck size={19} />} title="Condições contratuais e técnicas" text="Execução, pagamentos, obrigações e cláusulas do contrato."><StructuredSection groups={[{ title: "Prazo e fases de execução", description: "Fases e marcos posteriores a adjudicação.", items: contractPhases }, { title: "Valor e pagamentos", description: "Condições financeiras e fases de pagamento.", items: contractPayments }, { title: "Obrigações técnicas", description: "Entregas, normas e requisitos durante a execução.", items: contractObligations }, { title: "Garantias e cláusulas relevantes", description: "Riscos, garantias e penalizações identificadas.", items: contractRisks }]} empty="Condições de execução ainda não identificadas nas peças processadas." /></Detail><Detail id="documentacao" icon={<FileText size={19} />} title="Fontes da análise" text="Documentos utilizados, cobertura da análise e origem da informação."><SourcesSection processed={documentsProcessed} read={documentsRead} documents={sourceDocuments} updatedAt={analysisUpdatedAt} officialUrl={officialUrl} /></Detail>
    </section>
    <style jsx global>{`
      .analysis-redesign{max-width:1280px;padding:0 0 56px;color:#111a3c}.ar-header{padding:30px 0 20px}.ar-header>a,.ar-official{display:inline-flex;align-items:center;gap:8px;color:#14234a;font-size:13px;font-weight:700;text-decoration:none}.ar-header>div{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-top:16px}.ar-header h1{max-width:850px;margin:0;font-size:clamp(30px,4vw,48px);letter-spacing:-.055em;line-height:1.04}.ar-header h1.ar-title-fallback{display:-webkit-box;max-width:920px;overflow:hidden;overflow-wrap:anywhere;font-size:clamp(28px,3.2vw,42px);-webkit-box-orient:vertical;-webkit-line-clamp:2}.ar-header p{display:flex;flex-wrap:wrap;gap:8px 16px;margin:13px 0 0;color:#63708b;font-size:13px}.ar-header p span{display:flex;gap:6px;align-items:center}.ar-official{float:right;margin-top:-74px;padding:12px 15px;border:1px solid #d9deea;border-radius:8px;background:#fff}.ar-decision{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(390px,.9fr);gap:28px;align-items:center;padding:25px 30px;border:1px solid #d9e6df;border-radius:12px;background:linear-gradient(106deg,#fbfdfb,#f6faf7)}.ar-decision-copy{display:flex;align-items:center;gap:20px}.ar-decision-copy>i{display:grid;place-items:center;flex:0 0 auto;width:94px;height:94px;border:12px solid #d8ede0;border-top-color:#338357;border-right-color:#338357;border-radius:50%;color:#338357;background:#fff}.ar-decision-copy>i.pending{border-color:#fff0cf;border-top-color:#d5960a;border-right-color:#d5960a;color:#bd7e00}.ar-decision-copy>i.blocked{border-color:#ffe0df;border-top-color:#c53e3e;border-right-color:#c53e3e;color:#c53e3e}.ar-decision small{color:#317b51;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.ar-decision h2{margin:6px 0 7px;font-size:22px}.ar-decision p{margin:0;color:#56647d;font-size:13px;line-height:1.55}.ar-counts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.ar-counts>div{padding:8px 12px;border-left:1px solid #dce5df}.ar-counts strong{display:block;font-size:26px}.ar-counts span{display:block;margin-top:7px;color:#56647d;font-size:12px}.ar-counts .met strong{color:#297c52}.ar-counts .pending strong{color:#c78600}.ar-counts .blocked strong{color:#c64141}.ar-counts-neutral{grid-column:1/-1;min-height:74px;padding:10px 12px;border-left:3px solid #8a96a8;background:#f7f9fc}.ar-counts-neutral strong{font-size:14px;color:#384762}.ar-counts-neutral span{max-width:330px;line-height:1.4}.ar-counts a{grid-column:1/-1;justify-self:end;color:#183567;font-size:12px;font-weight:800;text-decoration:none}.ar-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin:18px 0;overflow:hidden;border:1px solid #e1e5ed;border-radius:11px;background:#fff}.ar-summary div{padding:16px 18px;border-right:1px solid #ebedf2}.ar-summary span{display:block;color:#68748c;font-size:11px}.ar-summary strong{display:block;margin-top:5px;font-size:14px}.ar-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.ar-card{display:flex;flex-direction:column;min-width:0;min-height:290px;padding:20px;border:1px solid #e0e5ed;border-radius:11px;background:#fff;box-shadow:0 4px 18px rgba(22,38,72,.025)}.ar-card h2{margin:0;font-size:16px}.ar-card ul{margin:0;padding:0;list-style:none}.ar-card li{overflow:hidden;padding:9px 0;border-top:1px solid #edf0f4;color:#283656;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.ar-card ul li:before{margin-right:8px;color:#5b7b9a;content:"•"}.ar-card em{color:#7c8698;font-size:12px;font-style:normal}.ar-card-content{display:flex;flex:1;flex-direction:column;min-height:0;margin-top:10px}.ar-card-cta{display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;width:100%;min-height:36px;margin-top:14px;padding:10px 8px;border-radius:7px;color:#183567;font-size:12px;font-weight:800;text-decoration:none;cursor:pointer;transition:background-color .16s ease,color .16s ease,transform .16s ease}.ar-card-cta:hover{background:#f0f5fa;color:#0f2c5d}.ar-card-cta:focus-visible{outline:2px solid #3d7db3;outline-offset:2px}.ar-card-cta svg{flex:0 0 auto;transition:transform .16s ease}.ar-card-cta:hover svg{transform:translateX(2px)}.ar-card ol{display:grid;gap:11px;margin:2px 0;padding:0 0 0 16px;border-left:1px solid #d9e1ec;list-style:none}.ar-card ol li{position:relative;overflow:visible;padding:0;border:0;white-space:normal}.ar-card ol li:before{position:absolute;top:4px;left:-21px;width:9px;height:9px;margin:0;border-radius:50%;background:#3d7db3;content:""}.ar-card ol span,.ar-card ol strong{display:block}.ar-card ol span{color:#586680;font-size:11px}.ar-card ol strong{margin-top:2px;font-size:12px}.ar-card-title{display:grid;grid-template-columns:18px 42px minmax(0,1fr);gap:10px;align-items:start;min-height:66px}.ar-card-index{padding-top:5px;color:#398058;font-size:11px;font-weight:800;line-height:1}.ar-card-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:#e7f1eb;color:#287850}.ar-card-icon svg{width:21px;height:21px}.ar-card-heading{min-width:0;min-height:66px}.ar-card-heading h2{min-height:39px;line-height:1.2}.ar-card-heading p{margin:5px 0 0;color:#68748c;font-size:12px;line-height:1.35}.ar-grid>.ar-card:nth-child(2) .ar-card-icon{background:#fff1da;color:#b97900}.ar-grid>.ar-card:nth-child(3) .ar-card-icon{background:#e7f0fa;color:#28659b}.ar-grid>.ar-card:nth-child(4) .ar-card-icon{background:#f0e9fa;color:#68499c}.ar-resolution-list{display:grid;gap:7px;margin:0;padding:0;list-style:none}.ar-resolution-list li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:8px;align-items:start;overflow:visible;padding:8px 0;border-top:1px solid #edf0f4;white-space:normal}.ar-resolution-list li:before{display:none}.ar-resolution-list svg{margin-top:1px;color:#c78600}.ar-resolution-list li.is-negative svg{color:#c64141}.ar-resolution-list li.is-warning svg{color:#c78600}.ar-resolution-list li.is-positive svg{color:#297c52}.ar-resolution-list strong{display:block;color:#283656;font-size:12px;line-height:1.25}.ar-resolution-list small{display:block;margin-top:3px;color:#68748c;font-size:11px;line-height:1.3}.ar-resolution-ok{display:flex;gap:8px;align-items:flex-start;margin:8px 0;color:#397654;font-size:12px;line-height:1.4}.ar-resolution-ok svg{flex:0 0 auto;color:#297c52}.ar-details{overflow:hidden;margin-top:16px;border:1px solid #e0e5ed;border-radius:11px;background:#fff}.ar-details details+details{border-top:1px solid #e7ebf1}.ar-details summary{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 20px;cursor:pointer;list-style:none}.ar-details summary::-webkit-details-marker{display:none}.ar-details summary>div{display:grid;grid-template-columns:22px auto;column-gap:11px;align-items:center}.ar-details summary svg{grid-row:span 2;color:#304a78}.ar-details summary strong{font-size:14px}.ar-details summary div span{grid-column:2;margin-top:4px;color:#6b7690;font-size:12px}.ar-details summary>b{font-size:20px;transition:transform .18s}.ar-details details[open] summary>b{transform:rotate(180deg)}.ar-detail-content{padding:2px 20px 22px}.ar-procedure{display:grid;grid-template-columns:minmax(240px,.4fr) minmax(0,1fr);gap:18px}.ar-sources{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.42fr);gap:18px}.analysis-redesign .dc-side-timeline,.analysis-redesign .project-info-panel{margin:0}.analysis-redesign .dc-four,.analysis-redesign .dc-heading{margin-top:0}.ar-address{flex-basis:100%;padding-left:21px;color:#53627d}.ar-address a{display:inline-flex;gap:5px;margin-left:7px;color:#183567;font-weight:700;text-decoration:none}.ar-content-section{display:grid;gap:18px}.ar-content-summary{display:flex;flex-wrap:wrap;gap:8px}.ar-content-summary span{padding:7px 10px;border:1px solid #dce5df;border-radius:999px;background:#f7faf8;color:#39634d;font-size:12px;font-weight:700}.ar-content-groups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.ar-content-group{min-width:0;padding:16px;border:1px solid #e4e9f0;border-radius:10px;background:#fbfcfe}.ar-content-group-heading h3{margin:0;color:#17264a;font-size:14px}.ar-content-group-heading p{margin:5px 0 12px;color:#68748c;font-size:12px;line-height:1.4}.ar-content-list{display:grid}.ar-content-row{display:grid;gap:7px;padding:10px 0;border-top:1px solid #e8edf3}.ar-content-row:first-child{border-top:0}.ar-content-row strong{display:block;color:#273657;font-size:13px;line-height:1.35}.ar-content-row p{margin:3px 0 0;color:#66748c;font-size:12px;line-height:1.45}.ar-content-badges{display:flex;flex-wrap:wrap;gap:5px}.ar-content-badges span{padding:4px 7px;border-radius:999px;background:#eaf1f8;color:#326083;font-size:10px;font-weight:700}.ar-content-more{display:block;margin-top:10px;color:#68748c;font-size:11px}.ar-section-empty{margin:0;color:#68748c;font-size:13px}.ar-source-meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;padding-top:2px;color:#68748c;font-size:12px}.ar-source-meta strong{color:#314261}.ar-source-meta a{display:inline-flex;align-items:center;gap:6px;color:#183567;font-weight:700;text-decoration:none}@media(max-width:1050px){.ar-content-groups{grid-template-columns:1fr}.ar-decision{grid-template-columns:1fr}.ar-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ar-sources,.ar-procedure{grid-template-columns:1fr}}@media(max-width:680px){.analysis-redesign{padding:0 16px 36px}.ar-header{padding-top:20px}.ar-header>div{display:block}.ar-official{float:none;margin:16px 0 0}.ar-header h1{font-size:32px}.ar-decision{padding:20px}.ar-decision-copy{align-items:flex-start}.ar-decision-copy>i{width:68px;height:68px;border-width:9px}.ar-summary{grid-template-columns:1fr 1fr}.ar-grid{grid-template-columns:1fr}.ar-card{min-height:0}.ar-details summary{padding:16px}.ar-details summary div span{display:none}.ar-detail-content{padding:0 16px 18px}}
    `}</style>
  </main>;
}

type ContentGroup = {
  title: string;
  description: string;
  items: any[];
  badges?: boolean;
};

function StructuredSection({
  summary = [],
  groups,
  empty,
}: {
  summary?: string[];
  groups: ContentGroup[];
  empty: string;
}) {
  const visibleGroups = groups.filter((group) => group.items.length > 0);
  const summaryItems = summary.filter((item) => !item.startsWith("0 "));

  if (!visibleGroups.length) return <p className="ar-section-empty">{empty}</p>;

  return <div className="ar-content-section">
    {summaryItems.length ? <div className="ar-content-summary">{summaryItems.map((item) => <span key={item}>{item}</span>)}</div> : null}
    <div className="ar-content-groups">{visibleGroups.map((group) => <section className="ar-content-group" key={group.title}>
      <div className="ar-content-group-heading"><h3>{group.title}</h3><p>{group.description}</p></div>
      <div className="ar-content-list">{group.items.slice(0, 8).map((item, index) => {
        const label = presentationItemText(item);
        const detail = presentationItemDetail(item);
        const badges = group.badges ? presentationItemBadges(item) : [];
        return <article key={`${label}-${index}`} className="ar-content-row"><div><strong>{label}</strong>{detail && detail !== label ? <p>{detail}</p> : null}</div>{badges.length ? <div className="ar-content-badges">{badges.map((badge) => <span key={badge}>{badge}</span>)}</div> : null}</article>;
      })}</div>
      {group.items.length > 8 ? <small className="ar-content-more">+ {group.items.length - 8} requisitos adicionais identificados</small> : null}
    </section>)}</div>
  </div>;
}

function SourcesSection({
  processed,
  read,
  documents,
  updatedAt,
  officialUrl,
}: {
  processed: number | null;
  read: number | null;
  documents: any[];
  updatedAt: string;
  officialUrl: string;
}) {
  const coverage = [
    processed !== null ? `${processed} documentos processados` : "",
    read !== null ? `${read} documentos efetivamente lidos` : "",
    documents.length ? `${documents.length} fontes principais` : "",
  ].filter(Boolean);

  return <div className="ar-content-section">
    {coverage.length ? <div className="ar-content-summary">{coverage.map((item) => <span key={item}>{item}</span>)}</div> : null}
    {documents.length ? <section className="ar-content-group"><div className="ar-content-group-heading"><h3>Documentos analisados</h3><p>Documentos efetivamente utilizados na leitura estruturada.</p></div><div className="ar-content-list">{documents.slice(0, 12).map((item, index) => {
      const label = sourceDocumentLabel(item);
      const detail = clean(item?.source_document ?? item?.file_name ?? item?.filename);
      return <article key={`${label}-${index}`} className="ar-content-row"><div><strong>{label || "Documento analisado"}</strong>{detail && detail !== label ? <p>{detail}</p> : null}</div></article>;
    })}</div>{documents.length > 12 ? <small className="ar-content-more">+ {documents.length - 12} documentos adicionais utilizados</small> : null}</section> : <p className="ar-section-empty">Documentos utilizados ainda nao identificados nas pecas processadas.</p>}
    {(updatedAt || officialUrl) ? <div className="ar-source-meta">{updatedAt ? <span>Atualizacao: <strong>{updatedAt}</strong></span> : null}{officialUrl ? <a href={officialUrl} target="_blank" rel="noreferrer">Origem oficial <ExternalLink size={14} /></a> : null}</div> : null}
  </div>;
}
function CardTitle({
  index,
  icon,
  title,
  description,
}: {
  index: string;
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return <div className="ar-card-title"><span className="ar-card-index">{index}</span><span className="ar-card-icon">{icon}</span><div className="ar-card-heading"><h2>{title}</h2><p>{description}</p></div></div>;
}

function CardCta({ href, children }: { href: string; children: ReactNode }) {
  function handleClick(event: React.MouseEvent<HTMLAnchorElement>) {
    if (!href.startsWith("#")) return;
    const target = document.getElementById(href.slice(1));
    if (!(target instanceof HTMLDetailsElement)) return;

    event.preventDefault();
    target.open = true;
    window.history.replaceState(null, "", href);
    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return <a className="ar-card-cta" href={href} onClick={handleClick}><span>{children}</span><ArrowRight size={16} aria-hidden="true" /></a>;
}
function OverviewCard({
  index,
  icon,
  title,
  description,
  items,
  href,
  action,
  empty,
}: {
  index: string;
  icon: ReactNode;
  title: string;
  description: string;
  items: string[];
  href: string;
  action: string;
  empty: string;
}) {
  return <article className="ar-card"><CardTitle index={index} icon={icon} title={title} description={description} /><div className="ar-card-content">{items.length ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <em>{empty}</em>}</div><CardCta href={href}>{action}</CardCta></article>;
}


function DeliverablesCard({
  items,
  total,
}: {
  items: DeliveryPreview[];
  total: number;
}) {
  const visibleItems = items.slice(0, 5);

  return (
    <article className="ar-card">
      <CardTitle
        index="01"
        icon={<FileText size={18} />}
        title="Entregas"
        description="O que temos de entregar."
      />

      <div className="ar-card-content">
        {visibleItems.length ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              width: "100%",
            }}
          >
            {visibleItems.map((item, index) => (
              <div
                key={`${item.label}-${index}`}
                style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(0, 1fr) minmax(72px, auto)",
                  columnGap: "12px",
                  alignItems: "center",
                  width: "100%",
                  padding: "10px 0",
                  borderBottom:
                    index < visibleItems.length - 1
                      ? "1px solid var(--border, #e8ebef)"
                      : "none",
                }}
              >
                <span
                  style={{
                    minWidth: 0,
                    textAlign: "left",
                    color: "#283656",
                    fontSize: "12px",
                    fontWeight: 400,
                    lineHeight: 1.35,
                  }}
                >
                  {item.label}
                </span>

                {item.summary ? (
                  <span
                    style={{
                      minWidth: 0,
                      textAlign: "right",
                      color: "#68748c",
                      fontSize: "11px",
                      fontWeight: 400,
                      lineHeight: 1.35,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {item.summary}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <em>Entregáveis por confirmar.</em>
        )}
      </div>

      <CardCta href="#submissao">
        {total
          ? `Ver todos os ${total} entregáveis`
          : "Ver entregas completas"}
      </CardCta>
    </article>
  );
}

function ResolutionCard({ title, items }: { title: string; items: Array<{ level: "negative" | "warning" | "positive"; title: string; description: string }> }) {
  return <article className="ar-card"><CardTitle index="04" icon={<Target size={18} />} title={title} description="Fatores que mais influenciam a decisão." /><div className="ar-card-content">{items.length ? <ul className="ar-resolution-list">{items.map((item, index) => <li className={`is-${item.level}`} key={`${item.title}-${index}`}>{item.level === "positive" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}<div><strong>{item.title}</strong><small>{item.description}</small></div></li>)}</ul> : <div className="ar-resolution-ok"><CheckCircle2 size={16} /><span>Não existem fatores determinantes adicionais identificados.</span></div>}</div><CardCta href="#explicacao">Ver explicação completa</CardCta></article>;
}
function Detail({ id, icon, title, text, open, children }: { id: string; icon: ReactNode; title: string; text: string; open?: boolean; children: ReactNode }) { return <details id={id} open={open}><summary><div>{icon}<strong>{title}</strong><span>{text}</span></div><b>⌄</b></summary><div className="ar-detail-content">{children}</div></details>; }