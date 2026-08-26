"use client";

import type { CompanyProfile } from "./company-types";

type Props = {
  profile: CompanyProfile;
};

function renderList(values: string[]) {
  if (values.length === 0) {
    return <p style={{ color: "#777", margin: 0 }}>Sem informação guardada.</p>;
  }

  return (
    <ul style={{ margin: 0, paddingLeft: "18px", color: "#444" }}>
      {values.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default function CompanyKnowledgeSection({ profile }: Props) {
  const hasKnowledge =
    profile.ai_memory.confirmed_facts.length > 0 ||
    profile.ai_memory.assumptions.length > 0 ||
    profile.ai_memory.validated_preferences.length > 0 ||
    profile.ai_memory.open_questions.length > 0;

  return (
    <section
      style={{
        background: "white",
        border: "1px solid #e7e7e0",
        borderRadius: "18px",
        padding: "24px",
      }}
    >
      <div style={{ marginBottom: "18px" }}>
        <h2 style={{ fontSize: "20px", marginBottom: "6px" }}>
          Conhecimento da empresa
        </h2>
        <p style={{ color: "#777", margin: 0, fontSize: "14px" }}>
          Esta área mostra a memória AI disponível para a empresa.
        </p>
      </div>

      {!hasKnowledge ? (
        <div
          style={{
            padding: "18px",
            borderRadius: "14px",
            background: "#fafaf7",
            border: "1px dashed #ddd",
          }}
        >
          <p style={{ margin: 0, color: "#777" }}>
            Ainda não existem factos confirmados ou notas de conhecimento guardadas.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "16px",
          }}
        >
          <div className="profile-field">
            <label>Factos confirmados</label>
            {renderList(profile.ai_memory.confirmed_facts)}
          </div>

          <div className="profile-field">
            <label>Suposições</label>
            {renderList(profile.ai_memory.assumptions)}
          </div>

          <div className="profile-field">
            <label>Preferências validadas</label>
            {renderList(profile.ai_memory.validated_preferences)}
          </div>

          <div className="profile-field">
            <label>Pontos em aberto</label>
            {renderList(profile.ai_memory.open_questions)}
          </div>
        </div>
      )}
    </section>
  );
}
