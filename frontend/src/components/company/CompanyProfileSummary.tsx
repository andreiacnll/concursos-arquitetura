"use client";

import type { CompanyProfile, CompanySourceStatus } from "./company-types";

type Props = {
  profile: CompanyProfile;
  companyName: string;
  sourceStatuses?: CompanySourceStatus[];
};

function renderValues(values: string[]) {
  if (values.length === 0) {
    return <p style={{ color: "#777", margin: 0 }}>Sem informação.</p>;
  }

  return (
    <ul style={{ margin: 0, paddingLeft: "18px", color: "#444" }}>
      {values.map((value) => (
        <li key={value}>{value}</li>
      ))}
    </ul>
  );
}

export default function CompanyProfileSummary({
  profile,
  companyName,
  sourceStatuses = [],
}: Props) {
  const projects = profile.project_experience;
  const websiteFacts =
    sourceStatuses.find((source) => source.key === "website")?.facts_created ?? 0;
  const portfolioFacts =
    sourceStatuses.find((source) => source.key === "portfolio")?.facts_created ?? 0;
  const interviewFacts = profile.ai_memory.confirmed_facts.length;

  return (
    <div className="onboarding-step">
      <h2>Perfil criado</h2>
      <p>
        Aqui fica o resumo da informação encontrada para{" "}
        {companyName || "a empresa"}.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "16px",
        }}
      >
        <div className="profile-field">
          <label>Identidade</label>
          <p style={{ margin: 0, color: "#444" }}>
            {profile.identity.description || "Sem descrição guardada."}
          </p>
          <p style={{ margin: "8px 0 0", color: "#777", fontSize: "13px" }}>
            {profile.identity.location || "Localização não definida"}
          </p>
        </div>

        <div className="profile-field">
          <label>Serviços</label>
          {renderValues(profile.services)}
        </div>

        <div className="profile-field">
          <label>Competências</label>
          {renderValues(profile.competences)}
        </div>

        <div className="profile-field">
          <label>Projetos encontrados</label>
          {projects.length === 0 ? (
            <p style={{ color: "#777", margin: 0 }}>
              Nenhum projeto identificado ainda.
            </p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: "18px", color: "#444" }}>
              {projects.map((project) => (
                <li key={`${project.name}-${project.typology}`}>
                  <strong>{project.name || "Projeto"}</strong>
                  {project.typology ? ` — ${project.typology}` : ""}
                  {project.location ? ` (${project.location})` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>

        {sourceStatuses.length > 0 && (
          <div className="profile-field">
            <label>Fontes analisadas</label>
            <p style={{ margin: "0 0 10px", color: "#444" }}>
              Website: {websiteFacts} factos extraídos; Portfolio:{" "}
              {portfolioFacts} factos extraídos; Entrevista: {interviewFacts}{" "}
              respostas aplicadas.
            </p>
            <ul style={{ margin: 0, paddingLeft: "18px", color: "#444" }}>
              {sourceStatuses.map((source) => (
                <li key={source.key}>
                  {source.label}: {source.status}
                  {source.detail ? ` — ${source.detail}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
