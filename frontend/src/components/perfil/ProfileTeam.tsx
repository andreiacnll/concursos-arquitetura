"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { Users } from "lucide-react";

const dimensoes = [
  { value: "1", label: "1 pessoa" },
  { value: "2-5", label: "2–5 pessoas" },
  { value: "5-10", label: "5–10 pessoas" },
  { value: "10+", label: "+10 pessoas" },
];

const areasEquipa = [
  "Arquitetura",
  "Urbanismo",
  "Paisagismo",
  "Engenharia",
  "Design",
  "Consultoria",
];

export default function ProfileTeam() {
  const { profile } = useProfile();
  const { isEditing, updateTeam } = useEditingProfile();
  const team = profile.team;

  const toggleArea = (area: string) => {
    const currentAreas = team.areas;
    const areas = currentAreas.includes(area)
      ? currentAreas.filter((a) => a !== area)
      : [...currentAreas, area];
    updateTeam({ areas });
  };

  const handleDimensaoChange = (value: string) => {
    updateTeam({ dimensao: value });
  };

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <Users size={20} />
        <div>
          <h2>Caracterização da Equipa</h2>
          <p>Dimensão e áreas de atuação da tua equipa.</p>
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-section-label">Dimensão da equipa</div>
        <div className="profile-chip-group">
          {dimensoes.map((d) => (
            <button
              key={d.value}
              className={`profile-chip ${team.dimensao === d.value ? "active" : ""}`}
              onClick={() => handleDimensaoChange(d.value)}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="profile-section-label" style={{ marginTop: 32 }}>Áreas da equipa</div>
        {team.areas.length === 0 && !isEditing ? (
          <div className="profile-empty-message">Nenhuma área selecionada</div>
        ) : (
          <div className="profile-chip-group">
            {areasEquipa.map((area) => (
              <button
                key={area}
                className={`profile-chip ${team.areas.includes(area) ? "active" : ""}`}
                onClick={() => toggleArea(area)}
              >
                {area}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
