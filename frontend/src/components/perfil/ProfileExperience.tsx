"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { BarChart3, Award, Target, CheckSquare } from "lucide-react";

const escalas = [
  { value: "pequena", label: "Pequena escala" },
  { value: "media", label: "Média escala" },
  { value: "grande", label: "Grande escala" },
];

export default function ProfileExperience() {
  const { profile } = useProfile();
  const { isEditing, updateExperience } = useEditingProfile();
  const { experience } = profile;

  const renderInput = (label: string, icon: React.ReactNode, field: keyof typeof experience, placeholder: string) => {
    const value = experience[field] as string;
    const isEmpty = !value || value.trim() === "";

    if (isEditing) {
      return (
        <div className="profile-field">
          <label>
            {icon}
            {label}
          </label>
          <input
            type="text"
            placeholder={placeholder}
            value={value}
            onChange={(e) => updateExperience({ [field]: e.target.value })}
          />
        </div>
      );
    }

    if (isEmpty) {
      return (
        <div className="profile-field">
          <label>
            {icon}
            {label}
          </label>
          <div className="profile-empty-field">Não definido</div>
        </div>
      );
    }

    return (
      <div className="profile-field">
        <label>
          {icon}
          {label}
        </label>
        <div className="profile-value">{value}</div>
      </div>
    );
  };

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <BarChart3 size={20} />
        <div>
          <h2>Critérios de Experiência</h2>
          <p>Dados que no futuro vão permitir recomendações com compatibilidade IA.</p>
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-field-row">
          {renderInput("Anos de atividade", <Award size={15} />, "anosAtividade", "Ex.: 10")}
          {renderInput("Número de projetos realizados", <CheckSquare size={15} />, "numProjetos", "Ex.: 45")}
        </div>

        <div className="profile-field-row">
          {renderInput("Projetos públicos realizados", <Target size={15} />, "projetosPublicos", "Ex.: 12")}
          {renderInput("Concursos ganhos", <Award size={15} />, "concursosGanhos", "Ex.: 5")}
        </div>

        <div className="profile-field" style={{ marginTop: 28 }}>
          <label>Escala habitual de projetos</label>
          {isEditing ? (
            <div className="profile-chip-group">
              {escalas.map((e) => (
                <button
                  key={e.value}
                  className={`profile-chip ${experience.escalaHabitual === e.value ? "active" : ""}`}
                  onClick={() => updateExperience({ escalaHabitual: e.value })}
                >
                  {e.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="profile-value">
              {experience.escalaHabitual ? escalas.find(e => e.value === experience.escalaHabitual)?.label || "Não definido" : "Não definido"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
