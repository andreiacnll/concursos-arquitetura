"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BriefcaseBusiness,
  CircleDollarSign,
  FileQuestion,
  HardHat,
  ShieldAlert,
  UsersRound,
} from "lucide-react";
import {
  dedupeDisplayItems,
  type AnalysisDisplayKind,
  formatAnalysisItemForDisplay,
} from "@/lib/analysis-display";

type AnyRecord = Record<string, any>;

type Props = {
  analysis: AnyRecord;
  ficha?: AnyRecord;
};

function clean(value: any): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function fold(value: any): string {
  return clean(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function asArray(value: any): AnyRecord[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item) => item !== null && item !== undefined)
    .map((item) =>
      typeof item === "object" ? item : { title: clean(item) },
    );
}

function numberValue(value: any): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;

  const raw = clean(value);
  if (!raw) return null;

  const normalized = raw
    .replace(/\s/g, "")
    .replace(/€/g, "")
    .replace(/\.(?=\d{3}(?:\D|$))/g, "")
    .replace(",", ".");

  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;

  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function prettyNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.0001) {
    return String(Math.round(value));
  }
  return value.toFixed(1).replace(".", ",");
}

function compact(value: any, limit = 170): string {
  const text = clean(value);
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trim()}…`;
}

function isProvenanceOnly(value: string): boolean {
  const normalized = fold(value);
  if (!normalized) return true;

  return [
    "confirmado",
    "confirmado nas pecas",
    "criterio confirmado nas pecas",
    "confirmado pelo utilizador",
    "inferido",
    "nao identificado",
    "nao aplicavel",
    "por confirmar",
  ].includes(normalized);
}

function titleFor(item: any): string {
  if (typeof item === "string" || typeof item === "number") {
    return clean(item);
  }

  return clean(
    item?.title ??
      item?.titulo ??
      item?.role ??
      item?.label ??
      item?.name ??
      item?.requirement ??
      item?.summary ??
      item?.description ??
      item?.descricao ??
      item?.text ??
      item?.value,
  );
}

function requiredCondition(item: AnyRecord): string {
  const required = item?.required ?? {};
  const text = clean(required?.text);
  if (text && !isProvenanceOnly(text)) return text;

  const metric = clean(required?.metric);
  const threshold = numberValue(required?.threshold);
  const unit = clean(required?.unit);
  const operator = clean(required?.operator);

  if (threshold === null || !metric) return "";

  const symbol =
    operator === ">=" || operator === "gte"
      ? "≥"
      : operator === "<=" || operator === "lte"
        ? "≤"
        : operator || "mínimo";

  return clean(`${symbol} ${prettyNumber(threshold)} ${unit}`);
}

function detailFor(item: AnyRecord): string {
  const candidates = [
    requiredCondition(item),
    item?.detail,
    item?.detalhe,
    item?.condition,
    item?.requirement_text,
    item?.source_text,
    item?.summary,
    item?.description,
    item?.descricao,
    item?.text,
    item?.evidence_excerpt,
    item?.source_excerpt,
    item?.source?.excerpt,
  ];

  for (const candidate of candidates) {
    const detail = clean(candidate);
    if (!detail || isProvenanceOnly(detail)) continue;
    if (fold(detail) === fold(titleFor(item))) continue;
    return compact(detail);
  }

  return "Requisito identificado";
}

function provenanceFor(item: AnyRecord): string {
  return clean(
    item?.status_label ??
      item?.status ??
      item?.source_heading ??
      item?.source_document ??
      item?.source?.section ??
      item?.source?.document ??
      item?.source?.status,
  ) || "Confirmado nas peças";
}

function criterionCode(item: AnyRecord): string {
  return fold(
    item?.subfactor_code ??
      item?.criterion_code ??
      item?.subcriterion_code ??
      "",
  );
}

function mergeItems(...values: any[]): AnyRecord[] {
  const byKey = new Map<string, AnyRecord>();
  const order: string[] = [];
  let anonymous = 0;

  for (const value of values) {
    for (const item of asArray(value)) {
      const code = criterionCode(item);
      const title = fold(titleFor(item));
      const factor = fold(item?.factor_code);

      const key = code
        ? `criterion:${code}`
        : title
          ? `title:${title}|factor:${factor}`
          : `anonymous:${anonymous++}`;

      const current = byKey.get(key);

      if (!current) {
        byKey.set(key, item);
        order.push(key);
        continue;
      }

      const merged = { ...current };

      for (const [field, candidate] of Object.entries(item)) {
        const old = merged[field];

        if (
          old === null ||
          old === undefined ||
          old === "" ||
          (Array.isArray(old) && !old.length)
        ) {
          merged[field] = candidate;
          continue;
        }

        if (
          typeof old === "string" &&
          typeof candidate === "string" &&
          clean(candidate).length > clean(old).length
        ) {
          merged[field] = candidate;
        }
      }

      byKey.set(key, merged);
    }
  }

  return order.map((key) => byKey.get(key)!).filter(Boolean);
}


function isLikelyScopeService(item: AnyRecord): boolean {
  const text = fold(`${titleFor(item)} ${item?.summary ?? ""} ${item?.description ?? ""}`);
  if (!text) return false;
  if (/^\d+$/.test(text)) return false;
  if (
    text.includes("decisao do orgao") ||
    text.includes("norma") ||
    text.includes("procedimento administrativo") ||
    text.includes("esclarecimento") ||
    text.includes("contratacao")
  ) {
    return false;
  }
  return [
    "arquitetura",
    "paisag",
    "estrutura",
    "estabilidade",
    "aguas",
    "esgotos",
    "eletricidade",
    "telecomunic",
    "seguranca",
    "acessibilidade",
    "bim",
    "medic",
    "orcamento",
    "assistencia tecnica",
    "levantamento",
    "geotecnia",
    "avac",
    "scie",
    "infraestrutura",
    "saneamento",
  ].some((marker) => text.includes(marker));
}

function isContractRisk(item: AnyRecord): boolean {
  const text = fold(`${titleFor(item)} ${item?.summary ?? ""} ${item?.description ?? ""} ${item?.evidence_excerpt ?? ""}`);
  if (!text) return false;
  return [
    "penalidade",
    "sancao",
    "multa",
    "caucao",
    "seguro",
    "responsabilidade",
    "incumprimento",
    "atraso",
    "prazo final",
    "prazos parciais",
    "erros e omissoes",
  ].some((marker) => text.includes(marker));
}
function canonicalDisplay(item: AnyRecord): AnyRecord {
  const required = item?.required ?? {};
  const target = item?.profile_target ?? {};

  return {
    ...item,
    title:
      titleFor(item) ||
      clean(required?.text) ||
      clean(target?.role) ||
      "Requisito identificado",
    summary:
      clean(item?.summary) ||
      clean(required?.text) ||
      clean(item?.source?.excerpt),
  };
}

function legacyLooksScored(item: AnyRecord): boolean {
  const probe = fold(
    [
      item?.titulo,
      item?.title,
      item?.descricao,
      item?.description,
      item?.summary,
      item?.weight_percent,
      item?.percentage,
      item?.points,
    ]
      .filter(Boolean)
      .join(" "),
  );

  return (
    probe.includes("subfator") ||
    probe.includes("subfactor") ||
    probe.includes("pontu") ||
    item?.weight_percent !== undefined ||
    item?.percentage !== undefined ||
    item?.points !== undefined
  );
}

function procedureSources(
  analysis: AnyRecord,
  ficha: AnyRecord,
): AnyRecord[] {
  const extraction = ficha?.design_competition_extraction ?? {};
  const insights = ficha?.document_insights ?? {};

  return [
    ficha?.procedure_analysis ?? {},
    extraction?.procedure_analysis ?? {},
    insights?.procedure_analysis ?? {},
    analysis ?? {},
  ];
}

function awardSources(sources: AnyRecord[]): AnyRecord[] {
  return sources.map((source) => source?.award_criteria ?? {});
}

function eligibilitySources(sources: AnyRecord[]): AnyRecord[] {
  return sources.map((source) => source?.eligibility ?? {});
}

function submissionSources(sources: AnyRecord[]): AnyRecord[] {
  return sources.map((source) => source?.submission ?? {});
}

function contractSources(sources: AnyRecord[]): AnyRecord[] {
  return sources.map((source) => source?.contract ?? {});
}

function scoringWeight(
  ficha: AnyRecord,
  scoring: AnyRecord[],
): number | null {
  const factors = asArray(ficha?.analysis_canonical?.criteria?.factors);
  if (!factors.length || !scoring.length) return null;

  const scoringCodes = new Set(
    scoring.map(criterionCode).filter(Boolean),
  );

  let effective = 0;
  const matchedParents = new Set<string>();

  for (const factor of factors) {
    const factorCode = fold(factor?.code);
    const factorWeight = numberValue(
      factor?.display_weight_percent ??
        factor?.published_weight_percent ??
        factor?.weight_percent,
    );

    let matchedSubfactor = false;

    for (const sub of asArray(factor?.subfactors)) {
      const subCode = fold(sub?.code);

      if (
        !subCode ||
        ![...scoringCodes].some(
          (code) =>
            code === subCode ||
            code.endsWith(subCode) ||
            subCode.endsWith(code),
        )
      ) {
        continue;
      }

      matchedSubfactor = true;

      const global = numberValue(
        sub?.effective_weight_percent ??
          sub?.global_weight_percent,
      );

      if (global !== null && global > 0) {
        effective += global;
      }
    }

    if (
      matchedSubfactor &&
      effective === 0 &&
      factorWeight !== null &&
      factorWeight > 0
    ) {
      matchedParents.add(factorCode || fold(factor?.label));
    }
  }

  if (effective > 0) return Math.min(100, effective);

  if (matchedParents.size === 1) {
    for (const factor of factors) {
      const key = fold(factor?.code) || fold(factor?.label);

      if (!matchedParents.has(key)) continue;

      const weight = numberValue(
        factor?.display_weight_percent ??
          factor?.published_weight_percent ??
          factor?.weight_percent,
      );

      if (weight !== null && weight > 0) return weight;
    }
  }

  const nonPrice = factors.filter((factor) => {
    const probe = fold(`${factor?.code} ${factor?.label}`);

    return !(
      probe.includes("preco") ||
      probe.includes("price") ||
      probe.includes("custo")
    );
  });

  if (nonPrice.length === 1) {
    const weight = numberValue(
      nonPrice[0]?.display_weight_percent ??
        nonPrice[0]?.published_weight_percent ??
        nonPrice[0]?.weight_percent,
    );

    if (weight !== null && weight > 0) return weight;
  }

  return null;
}

function rows(
  items: AnyRecord[],
  empty: string,
  limit = 7,
  kind: AnalysisDisplayKind = "generic",
) {
  return (
    <ProcedureRows
      items={items}
      empty={empty}
      limit={limit}
      kind={kind}
    />
  );
}

function ProcedureRows({
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
  const [detailIndex, setDetailIndex] = useState<number | null>(null);

  if (!items.length) {
    return <p className="dc-empty">{empty}</p>;
  }

  const displayItems = dedupeDisplayItems(items);
  const visible = expanded ? displayItems : displayItems.slice(0, limit);
  const remaining = Math.max(displayItems.length - limit, 0);
  const displayRows = visible.map((item) => formatAnalysisItemForDisplay(item, kind));
  const sources = displayItems
    .map((item) => formatAnalysisItemForDisplay(item, kind))
    .filter((display) => display.hasMoreDetail);

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
          display: block;
          color: #59615a;
          font-size: 12px;
          line-height: 1.35;
        }

        .analysis-display-item strong {
          display: block;
          color: #1f332a;
          font-size: 13px;
          line-height: 1.35;
          max-width: none;
          text-align: left;
        }

        .analysis-qualifiers {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
        }

        .analysis-qualifiers span {
          display: inline-flex;
          align-items: center;
          width: fit-content;
          border-radius: 999px;
          background: #f1f4ec;
          color: #536943;
          font-size: 10px;
          line-height: 1;
          padding: 5px 7px;
          white-space: nowrap;
        }

        .analysis-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .analysis-source-list {
          display: grid;
          gap: 8px;
        }

        .analysis-sources-button,
        .analysis-show-all {
          border: 0;
          background: transparent;
          color: #587436;
          cursor: pointer;
          font-size: 11px;
          font-weight: 700;
          padding: 0;
          text-decoration: underline;
          text-underline-offset: 2px;
        }

        .analysis-source-detail {
          display: grid;
          gap: 4px;
          margin-top: 2px;
          padding: 8px 10px;
          border-radius: 10px;
          background: #f7f7f2;
          color: #62665f;
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

  return (
    <div className="analysis-display-list">
      <div className="dc-rows">
        {visible.map((item, index) => {
          const display = formatAnalysisItemForDisplay(item, kind);
          const detailOpen = detailIndex === index;
          const sourceLabel = [
            display.source.document,
            display.source.section,
            display.source.page ? `p. ${display.source.page}` : "",
          ]
            .filter(Boolean)
            .join(" · ");

          return (
            <div className="dc-row analysis-display-row" key={`${display.label}-${index}`}>
              <span>{display.label}</span>
              <strong title={display.provenance}>{display.primaryValue}</strong>
              {display.hasMoreDetail ? (
                <button
                  type="button"
                  className="analysis-detail-button"
                  onClick={() => setDetailIndex(detailOpen ? null : index)}
                  aria-expanded={detailOpen}
                >
                  {detailOpen ? "Ocultar" : "Fonte"}
                </button>
              ) : null}
              {detailOpen ? (
                <div className="analysis-source-detail">
                  <small>{display.provenance}</small>
                  {sourceLabel ? <small>Fonte: {sourceLabel}</small> : null}
                  {display.source.excerpt ? <p>{display.source.excerpt}</p> : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

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
  );
}

export default function ProcedureSpecificCards({
  analysis,
  ficha = {},
}: Props) {
  // CNLL_DIRECT_FICHA_CARDS_V17_10
  //
  // Estes cards recebem a ficha completa de propósito. A ficha persistida
  // é a fonte de verdade e não pode ser escondida por um adapter intermédio.
  const sources = procedureSources(analysis, ficha);
  const awards = awardSources(sources);
  const eligibilities = eligibilitySources(sources);
  const submissions = submissionSources(sources);
  const contracts = contractSources(sources);

  const canonicalRequirements = asArray(
    ficha?.analysis_canonical?.requirements,
  );

  const canonicalEligibility = canonicalRequirements
    .filter(
      (item) =>
        fold(item?.nature) === "eligibility" &&
        fold(item?.phase) !== "execution",
    )
    .map(canonicalDisplay);

  const canonicalScoring = canonicalRequirements
    .filter((item) => {
      if (fold(item?.phase) === "execution") return false;
      if (item?.profile_dependent !== true) return false;

      const nature = fold(item?.nature);
      return nature === "evaluation" || nature === "team";
    })
    .map(canonicalDisplay);

  const canonicalTeam = canonicalRequirements
    .filter((item) => {
      if (fold(item?.phase) === "execution") return false;

      const nature = fold(item?.nature);
      const scope = fold(item?.profile_target?.scope);

      return nature === "team" || scope === "person";
    })
    .map(canonicalDisplay);

  const legacyTeam = asArray(ficha?.equipa);
  const legacyScoring = legacyTeam.filter(legacyLooksScored);

  const scoring = mergeItems(
    ...awards.map((award) => award?.scoring_requirements),
    ...eligibilities.map(
      (eligibility) => eligibility?.scoring_requirements,
    ),
    canonicalScoring,
    legacyScoring,
  );

  const team = mergeItems(
    ...sources.map((source) => source?.technical_team),
    ...submissions.map(
      (submission) => submission?.team_requirements,
    ),
    ...contracts.map((contract) => contract?.technical_team),
    canonicalTeam,
    legacyTeam,
  );

  const exclusions = mergeItems(
    ...eligibilities.map(
      (eligibility) => eligibility?.explicit_exclusions,
    ),
    ...eligibilities.map(
      (eligibility) => eligibility?.eligibility_requirements,
    ),
    ...eligibilities.map(
      (eligibility) => eligibility?.minimum_requirements,
    ),
    ...submissions.map(
      (submission) => submission?.critical_conditions,
    ),
    canonicalEligibility,
  );

  const scope = mergeItems(
    ...contracts.map((contract) => contract?.scope_services),
  ).filter(isLikelyScopeService);

  const phases = mergeItems(
    ...contracts.map((contract) => contract?.phases),
  );

  const payments = mergeItems(
    ...contracts.map((contract) => contract?.payments),
    ...contracts.map(
      (contract) => contract?.payment_conditions,
    ),
  );

  const rawRisks = mergeItems(
    ...contracts.map((contract) => contract?.risks),
  );

  const risks = rawRisks.filter(isContractRisk);
  const obligations = mergeItems(
    ...contracts.map((contract) => contract?.obligations),
    ...contracts.map((contract) => contract?.conditions),
    rawRisks.filter((item) => !isContractRisk(item)),
  );

  const gaps = mergeItems(
    ...sources.map((source) => source?.document_gaps),
  );

  const inconsistencies = mergeItems(
    ...sources.map((source) => source?.inconsistencies),
  );

  const experienceWeight = scoringWeight(ficha, scoring);

  const family =
    clean(analysis?.family) ||
    clean(ficha?.analysis_family) ||
    "project_services";

  if (family === "design_competition") return null;

  const familyLabel =
    family === "design_build"
      ? "Conceção-Construção"
      : clean(analysis?.family_label) || "Prestação de serviços de projeto";

  const showExclusions = exclusions.length > 0;
  const showScoring = scoring.length > 0 || experienceWeight !== null;
  const showTeam = team.length > 0;
  const showScope = scope.length > 0;
  const showPhases = phases.length > 0 || payments.length > 0;
  const showRisks = risks.length > 0;
  const showObligations = obligations.length > 0;
  const showDocumentation =
    gaps.length > 0 || inconsistencies.length > 0;

  return (
    <section>
      <div className="dc-heading">
        <span>{familyLabel}</span>
        <h2>Capacidade, avaliação e âmbito</h2>
      </div>

      <div className="dc-four">
        {showExclusions ? (
        <article className="dc-card">
          <div className="dc-card-title">
            <AlertTriangle size={18} />
            <h3>Elegibilidade e exclusões</h3>
          </div>

          <div className="procedure-summary">
            {exclusions.length ? <strong>{exclusions.length}</strong> : null}
            <span>
              {exclusions.length
                ? "condições identificadas"
                : "Nenhuma exclusão explícita identificada"}
            </span>
          </div>

          {rows(
            exclusions,
            "Não foi possível confirmar exclusões adicionais nas peças disponíveis.",
            5,
            "exclusion",
          )}
        </article>
        ) : null}

        {showScoring ? (
        <article className="dc-card">
          <div className="dc-card-title">
            <BriefcaseBusiness size={18} />
            <h3>Experiência que dá pontuação</h3>
          </div>

          <div className="procedure-summary">
            <strong>
              {experienceWeight !== null
                ? `${prettyNumber(experienceWeight)}%`
                : scoring.length
                  ? `${scoring.length} critérios`
                  : "Por confirmar"}
            </strong>
            <span>
              {experienceWeight !== null
                ? "da avaliação depende de experiência / equipa"
                : scoring.length
                  ? "critérios pontuados identificados"
                  : "peso global a confirmar"}
            </span>
          </div>

          {rows(
            scoring,
            "Não foram identificados critérios de experiência pontuados nas peças disponíveis.",
            7,
            "requirement",
          )}
        </article>
        ) : null}

        {showTeam ? (
        <article className="dc-card">
          <div className="dc-card-title">
            <UsersRound size={18} />
            <h3>Equipa técnica a apresentar</h3>
          </div>

          <div className="procedure-summary">
            <strong>{team.length || "Por confirmar"}</strong>
            <span>
              {team.length
                ? "funções / requisitos identificados"
                : "composição ainda não confirmada"}
            </span>
          </div>

          {rows(
            team,
            "Equipa ainda não confirmada nas peças disponíveis.",
            7,
            "requirement",
          )}
        </article>
        ) : null}

        {showScope ? (
          <article className="dc-card">
            <div className="dc-card-title">
              {family === "design_build" ? (
                <HardHat size={18} />
              ) : (
                <UsersRound size={18} />
              )}
              <h3>Âmbito dos serviços</h3>
            </div>

            <div className="procedure-summary">
              <strong>{scope.length}</strong>
              <span>grupos de serviços identificados</span>
            </div>

            {rows(scope, "", 6, "scope")}
          </article>
        ) : null}

        {showPhases ? (
          <article className="dc-card">
            <div className="dc-card-title">
              <CircleDollarSign size={18} />
              <h3>Fases e pagamentos</h3>
            </div>

            <div className="procedure-summary">
              <strong>{phases.length || "Por confirmar"}</strong>
              <span>fases contratuais identificadas</span>
            </div>

            {rows(phases, "Fases ainda não confirmadas.", 6)}

            {payments.length ? (
              <div className="procedure-secondary">
                {rows(payments, "", 4, "payment")}
              </div>
            ) : null}
          </article>
        ) : null}

        {showRisks ? (
          <article className="dc-card">
            <div className="dc-card-title">
              <ShieldAlert size={18} />
              <h3>Riscos contratuais</h3>
            </div>

            <div className="procedure-summary">
              <strong>{risks.length}</strong>
              <span>penalidades / garantias / responsabilidades</span>
            </div>

            {rows(risks, "", 6, "risk")}
          </article>
        ) : null}

        {showObligations ? (
          <article className="dc-card">
            <div className="dc-card-title">
              <FileQuestion size={18} />
              <h3>Obrigações contratuais</h3>
            </div>

            <div className="procedure-summary">
              <strong>{obligations.length}</strong>
              <span>condições pós-adjudicação</span>
            </div>

            {rows(obligations, "", 6, "phase")}
          </article>
        ) : null}

        {showDocumentation ? (
          <article className="dc-card">
            <div className="dc-card-title">
              <FileQuestion size={18} />
              <h3>Informação ainda em falta</h3>
            </div>

            <div className="procedure-summary">
              <strong>{gaps.length + inconsistencies.length}</strong>
              <span>pontos a confirmar documentalmente</span>
            </div>

            {rows(
              [...gaps, ...inconsistencies],
              "",
              6,
              "risk",
            )}
          </article>
        ) : null}
      </div>

      <style jsx>{`
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

        .procedure-secondary {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #e7e7e2;
        }

        .dc-four {
          grid-template-columns: repeat(6, minmax(0, 1fr));
        }

        .dc-four :global(.dc-card) {
          grid-column: span 2;
        }

        .dc-four :global(.dc-card:nth-child(2)),
        .dc-four :global(.dc-card:nth-child(3)),
        .dc-four :global(.dc-card:nth-child(5)) {
          grid-column: span 3;
        }

        .analysis-display-list {
          display: grid;
          gap: 12px;
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
          max-width: none;
          text-align: left;
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

        .analysis-source-list {
          display: grid;
          gap: 8px;
        }

        .analysis-display-row {
          grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr) auto;
          align-items: start;
        }

        .analysis-detail-button,
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

        .analysis-source-detail {
          grid-column: 1 / -1;
          display: grid;
          gap: 4px;
          margin-top: 2px;
          padding: 8px 10px;
          border-radius: 10px;
          background: #f7f7f2;
          color: #62665f;
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

        .analysis-show-all {
          width: fit-content;
          padding: 0;
        }

        @media (max-width: 760px) {
          .analysis-display-row {
            grid-template-columns: 1fr;
          }

          .dc-four,
          .dc-four :global(.dc-card),
          .dc-four :global(.dc-card:nth-child(2)),
          .dc-four :global(.dc-card:nth-child(3)),
          .dc-four :global(.dc-card:nth-child(5)) {
            grid-template-columns: 1fr;
            grid-column: span 1;
          }
        }
      `}</style>
    </section>
  );
}
