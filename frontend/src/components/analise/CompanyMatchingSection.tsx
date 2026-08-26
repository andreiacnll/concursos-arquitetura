"use client";

import {
  BadgeCheck,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  FileSearch,
  Lightbulb,
  MapPin,
  Sparkles,
  Target,
  TriangleAlert,
  Users,
} from "lucide-react";

type CompanyMatchingSectionProps = {
  matching?: any;
};

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.replace(/\s+/g, " ").trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map(stringifyValue).filter(Boolean).join(" · ");
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const preferred = obj.value ?? obj.label ?? obj.name ?? obj.text ?? obj.description ?? obj.typology ?? obj.field;
    if (preferred !== undefined) return stringifyValue(preferred);
    const parts = Object.entries(obj)
      .filter(([, child]) => child !== null && child !== undefined && stringifyValue(child))
      .map(([key, child]) => `${key}: ${stringifyValue(child)}`);
    return parts.join(" · ");
  }
  return "";
}

function cleanText(value: unknown, fallback = "Por confirmar") {
  const text = stringifyValue(value);
  if (!text || text.toLowerCase() === "not found" || text === "[object Object]") return fallback;
  return text;
}

function listText(value: unknown, fallback = "Informação não encontrada") {
  if (Array.isArray(value)) {
    const items = value.map((item) => cleanText(item, "")).filter(Boolean);
    return items.length ? items : [fallback];
  }
  const text = cleanText(value, fallback);
  return text ? [text] : [fallback];
}

function decisionLabel(decision: unknown) {
  const text = cleanText(decision, "Por confirmar").toLowerCase();
  if (text.includes("avanc")) return "Avançar";
  if (text.includes("avali")) return "Avaliar";
  if (text.includes("priorit")) return "Não prioritário";
  if (text.includes("dados")) return "Dados insuficientes";
  return cleanText(decision, "Por confirmar");
}

function confidenceLabel(value: unknown) {
  const text = cleanText(value, "Por confirmar");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function scoreLabel(score: number | null | undefined) {
  if (typeof score !== "number") return "Por confirmar";
  if (score >= 90) return "Muito elevada";
  if (score >= 75) return "Elevada";
  if (score >= 60) return "Moderada";
  if (score >= 40) return "Baixa";
  return "Muito baixa";
}

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    Experiencia: "Experiência",
    Equipa: "Equipa",
    Servicos: "Serviços",
    Especializacoes: "Especializações",
    Criterios: "Critérios",
    Preco: "Preço",
    Localizacao: "Localização",
    "project_experience.typologies": "Experiência semelhante",
    services: "Serviços",
    competences: "Competências",
    specializations: "Especializações",
    required_team: "Equipa exigida",
    location: "Localização",
  };
  return labels[field] || field || "Campo";
}

function contextLabel(type?: string) {
  switch (type) {
    case "design_competition":
      return "Leitura comparativa entre o concurso de conceção e o CompanyProfile";
    case "ideas_competition":
      return "Leitura comparativa entre o concurso de ideias e o CompanyProfile";
    case "execution_project":
      return "Leitura comparativa técnica entre o projeto e o CompanyProfile";
    case "rehabilitation_project":
      return "Leitura comparativa para reabilitação e o CompanyProfile";
    default:
      return "Leitura comparativa entre o concurso e o CompanyProfile";
  }
}

export default function CompanyMatchingSection({ matching }: CompanyMatchingSectionProps) {
  if (!matching || typeof matching !== "object") {
    return null;
  }

  const score =
    typeof matching.compatibility_score === "number"
      ? matching.compatibility_score
      : typeof matching.score === "number"
        ? matching.score
        : null;
  const breakdown = Array.isArray(matching.compatibility_breakdown)
    ? matching.compatibility_breakdown
    : Array.isArray(matching.score_explanation?.breakdown)
      ? matching.score_explanation.breakdown
      : [];
  const strengths = Array.isArray(matching.strengths) ? matching.strengths : [];
  const weaknesses = Array.isArray(matching.weaknesses) ? matching.weaknesses : [];
  const matchedProjects = Array.isArray(matching.matched_projects) ? matching.matched_projects : [];
  const matchedServices = listText(matching.matched_services);
  const matchedCompetences = listText(matching.matched_competences);
  const matchedSpecializations = listText(matching.matched_specializations);
  const missingInformation = listText(matching.missing_information);
  const recommendation = matching.recommendation || matching.final_recommendation || {};

  const strategicFit = matching.strategic_fit || {};
  const locationStatus = cleanText(strategicFit?.location?.status, "Por confirmar");
  const companyLocation = cleanText(strategicFit?.location?.company, "Informação não encontrada");
  const competitionLocation = cleanText(strategicFit?.location?.competition, "Informação não encontrada");
  const preferredLocations = listText(strategicFit?.location?.preferred_locations);
  const competitionTypologies = listText(strategicFit?.competition_typologies);
  const typeLabel = contextLabel(matching.competition_type);

  return (
    <section className="profile-card company-matching-section">
      <div className="profile-card-header compact">
        <Target size={22} />
        <div>
          <h2>Adequação à empresa</h2>
          <p>{typeLabel}</p>
        </div>
      </div>

      <div className="company-matching-summary">
        <div className="matching-pill">
          <ChartNoAxesCombined size={16} />
          <span>
            Compatibilidade {score !== null ? `${score}/100` : "Por confirmar"}
            {score !== null ? ` · ${scoreLabel(score)}` : ""}
          </span>
        </div>
        <div className="matching-pill">
          <BadgeCheck size={16} />
          <span>{confidenceLabel(matching.confidence)}</span>
        </div>
        <div className="matching-pill">
          <Sparkles size={16} />
          <span>{decisionLabel(recommendation.decision || recommendation.status)}</span>
        </div>
      </div>

      <div className="company-matching-grid">
        <div className="matching-block">
          <h3>
            <BriefcaseBusiness size={16} />
            Experiência
          </h3>
          {matchedProjects.length > 0 ? (
            <ul className="matching-list">
              {matchedProjects.slice(0, 8).map((project: any, index: number) => (
                <li key={index}>
                  <strong>{cleanText(project?.name, "Projeto sem nome")}</strong>
                  <span>
                    {cleanText(project?.typology, "Tipologia por confirmar")}
                    {project?.location ? ` · ${cleanText(project.location)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="matching-empty">Informação não encontrada.</p>
          )}
        </div>

        <div className="matching-block">
          <h3>
            <Users size={16} />
            Serviços, competências e especializações
          </h3>
          <p className="matching-subtitle">Serviços</p>
          <div className="matching-chip-row">
            {matchedServices.map((item) => (
              <span key={item} className="matching-chip">
                {item}
              </span>
            ))}
          </div>
          <p className="matching-subtitle">Competências</p>
          <div className="matching-chip-row">
            {matchedCompetences.map((item) => (
              <span key={item} className="matching-chip">
                {item}
              </span>
            ))}
          </div>
          <p className="matching-subtitle">Especializações</p>
          <div className="matching-chip-row">
            {matchedSpecializations.map((item) => (
              <span key={item} className="matching-chip">
                {item}
              </span>
            ))}
          </div>
        </div>

        <div className="matching-block">
          <h3>
            <TriangleAlert size={16} />
            Lacunas e riscos
          </h3>
          {weaknesses.length > 0 ? (
            <ul className="matching-list">
              {weaknesses.slice(0, 4).map((item: any, index: number) => (
                <li key={index}>
                  <strong>{cleanText(item?.name, "Risco")}</strong>
                  <span>{cleanText(item?.justification, "Por confirmar")}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="matching-empty">Cobertura parcial por confirmar.</p>
          )}
          <p className="matching-subtitle">Informação em falta</p>
          <div className="matching-chip-row">
            {missingInformation.map((item) => (
              <span key={item} className="matching-chip muted">
                {item}
              </span>
            ))}
          </div>
        </div>

        <div className="matching-block">
          <h3>
            <FileSearch size={16} />
            Estratégia
          </h3>
          <div className="matching-strategy-grid">
            <div>
              <span className="matching-subtitle">Localização</span>
              <p>{locationStatus}</p>
              <small>
                Empresa: {companyLocation} · Concurso: {competitionLocation}
              </small>
            </div>
            <div>
              <span className="matching-subtitle">Preferências</span>
              <div className="matching-chip-row">
                {preferredLocations.map((item) => (
                  <span key={item} className="matching-chip">
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <span className="matching-subtitle">Tipologias do concurso</span>
              <div className="matching-chip-row">
                {competitionTypologies.map((item) => (
                  <span key={item} className="matching-chip">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="matching-breakdown">
        <h3>Breakdown</h3>
        <div className="matching-breakdown-list">
          {breakdown.map((item: any, index: number) => (
            <div className="matching-breakdown-item" key={index}>
              <div className="matching-breakdown-head">
                <strong>{fieldLabel(item?.name || item?.field || `Dimensão ${index + 1}`)}</strong>
                <span>
                  {cleanText(item?.value, "0")} / {cleanText(item?.maximum, "0")}
                </span>
              </div>
              <p>{cleanText(item?.justification, "Por confirmar")}</p>
              {Array.isArray(item?.evidence) && item.evidence.length > 0 ? (
                <div className="matching-evidence">
                  {item.evidence.slice(0, 4).map((evidenceItem: any, evidenceIndex: number) => (
                    <span key={evidenceIndex}>
                      {cleanText(
                        evidenceItem?.name ||
                          evidenceItem?.value ||
                          evidenceItem?.project ||
                          evidenceItem?.field ||
                          evidenceItem,
                        "Evidência",
                      )}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="company-matching-columns">
        <div className="matching-block">
          <h3>
            <MapPin size={16} />
            Forças
          </h3>
          {strengths.length > 0 ? (
            <ul className="matching-list">
              {strengths.slice(0, 4).map((item: any, index: number) => (
                <li key={index}>
                  <strong>{cleanText(item?.name, "Força")}</strong>
                  <span>{cleanText(item?.justification, "Por confirmar")}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="matching-empty">Por confirmar.</p>
          )}
        </div>

        <div className="matching-block">
          <h3>
            <Lightbulb size={16} />
            Recomendação
          </h3>
          <p className="matching-recommendation">{cleanText(recommendation.explanation, "Por confirmar")}</p>
          <p className="matching-subtitle">Confiança</p>
          <p>{confidenceLabel(matching.confidence)}</p>
          <p className="matching-subtitle">Decisão</p>
          <p>{decisionLabel(recommendation.decision || recommendation.status)}</p>
        </div>
      </div>

      <style jsx>{`
        .company-matching-summary,
        .company-matching-columns {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 16px;
        }

        .company-matching-columns {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .matching-pill,
        .matching-block,
        .matching-breakdown-item {
          border: 1px solid #e5e7dd;
          border-radius: 14px;
          background: #fff;
        }

        .matching-pill {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          color: #314526;
          font-weight: 600;
        }

        .matching-block,
        .matching-breakdown-item {
          padding: 16px;
        }

        .company-matching-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 16px;
        }

        .matching-block h3,
        .matching-breakdown h3 {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 10px;
          font-size: 15px;
        }

        .matching-subtitle {
          margin: 12px 0 6px;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          color: #6b725e;
        }

        .matching-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .matching-chip {
          display: inline-flex;
          align-items: center;
          padding: 6px 10px;
          border-radius: 999px;
          background: #f4f6ee;
          color: #3f542b;
          font-size: 12px;
        }

        .matching-chip.muted {
          background: #f7f7f3;
          color: #6f7368;
        }

        .matching-list {
          margin: 0;
          padding-left: 18px;
          display: grid;
          gap: 8px;
        }

        .matching-list li {
          display: grid;
          gap: 2px;
        }

        .matching-empty {
          margin: 0;
          color: #6f7368;
        }

        .matching-strategy-grid {
          display: grid;
          gap: 14px;
        }

        .matching-strategy-grid p {
          margin: 0;
          line-height: 1.5;
        }

        .matching-strategy-grid small {
          color: #6f7368;
        }

        .matching-breakdown-list {
          display: grid;
          gap: 10px;
        }

        .matching-breakdown-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 6px;
        }

        .matching-breakdown-head span {
          white-space: nowrap;
          color: #536248;
        }

        .matching-evidence {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 10px;
        }

        .matching-evidence span {
          padding: 6px 10px;
          border-radius: 999px;
          background: #f4f6ee;
          color: #3f542b;
          font-size: 12px;
        }

        .matching-recommendation {
          margin: 0;
          line-height: 1.55;
        }

        @media (max-width: 1100px) {
          .company-matching-summary,
          .company-matching-grid,
          .company-matching-columns {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
