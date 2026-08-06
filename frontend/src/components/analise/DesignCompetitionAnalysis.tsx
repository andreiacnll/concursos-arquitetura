"use client";

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
import SubmissionRequirementsCards from "@/components/analise/SubmissionRequirementsCards";

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

function makeFact(label: string, value: unknown, limit = 150): Fact {
  const text = compact(value, limit);
  return {
    label,
    value: valid(text) ? text : EMPTY,
    confirmed: valid(text),
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


function normalizeCategory(value: unknown): string {
  return clean(value)
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
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
    "Concurso de conceção";
  const entity =
    clean(concurso?.entidade) ||
    clean(ficha?.identificacao?.entidade);
  const location =
    clean(concurso?.localizacao) ||
    clean(ficha?.localizacao?.morada) ||
    clean(ficha?.identificacao?.localizacao);
  const procedure =
    clean(concurso?.tipo_procedimento) ||
    clean(ficha?.identificacao?.tipo_procedimento) ||
    "Concurso de conceção";
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
    getFact(extraction, "submission_deadline") ||
    clean(concurso?.data_limite);
  const criteria =
    clean(ficha?.criterio_resumo) ||
    clean(ficha?.criterios?.resumo);
  const documentStatus =
    clean(presentation?.document_status) ||
    clean(ficha?.document_insights?.document_status);

  const metrics = [
    makeFact("Valor do procedimento", procedureValue, 90),
    makeFact("Custo estimado da obra", constructionCost, 90),
    makeFact("Honorários de projeto", servicesDisplay, 90),
    makeFact("Área de intervenção", totalArea, 90),
    makeFact("Entrega das propostas", deadline, 105),
    makeFact("Modelo de avaliação", criteria, 105),
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
    ...(prizes.length
      ? prizes
      : [makeFact("Prémios do concurso", "", 90)]),
    makeFact("Valor do procedimento", procedureValue, 90),
    makeFact("Honorários de projeto", servicesDisplay, 90),
    makeFact("Custo estimado da obra", constructionCost, 90),
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
  const scoreCandidate =
    matching?.compatibility_score ??
    matching?.score ??
    matching?.score_compatibilidade ??
    decision?.score ??
    ficha?.analise_ai?.score;
  const score =
    typeof scoreCandidate === "number" && Number.isFinite(scoreCandidate)
      ? Math.round(scoreCandidate)
      : null;

  const recommendation =
    compact(
      matching?.recommendation?.explanation ??
        matching?.final_recommendation?.explanation ??
        ficha?.recomendacao_final?.justificacao ??
        ficha?.decision_summary,
      420,
    ) || EMPTY;
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

  const timeline = [
    makeFact(
      "Publicação do anúncio",
      clean(concurso?.data) ||
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
    makeFact(
      "Entrega das propostas",
      deadline,
      100,
    ),
  ];

  return (
    <main className="site-container dc-page">
      <header className="dc-hero">
        <a className="dc-back" href="/analise">
          <ArrowLeft size={15} />
          Voltar às análises
        </a>

        <div className="dc-hero-grid">
          <div>
            <span className="dc-kicker">
              {isInterventionProgram
                ? "Análise de projeto e intervenção"
                : "Análise automática de concurso"}
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
        {metrics.map((item) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small className={item.confirmed ? "ok" : "pending"}>
              {item.confirmed ? "Confirmado" : "Por confirmar"}
            </small>
          </article>
        ))}
      </section>

      <div className="dc-layout">
        <div className="dc-main">
          <AiPanel title="Vale a pena concorrer?">
            <div className="dc-decision">
              <div className="dc-score">
                <span>Pontuação global</span>
                <strong>{score ?? "—"}</strong>
                <small>/100</small>
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
                <span>Porque é relevante</span>
                <List items={opportunities} />
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

              <SubmissionRequirementsCards
                              requirements={submissionRequirements}
                            />

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


            </div>
          </section>

          <section className="dc-program">
            <div className="dc-heading">
              <span>
                {isInterventionProgram
                  ? "Programa de intervenção"
                  : "Programa funcional"}
              </span>
              <h2>
                {isInterventionProgram
                  ? "Síntese territorial e técnica"
                  : "Resumo do programa preliminar"}
              </h2>
            </div>

            {isInterventionProgram ? (
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
      `}</style>
    </main>
  );
}
