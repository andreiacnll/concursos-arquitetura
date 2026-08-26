"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { Lightbulb } from "lucide-react";

const especialidades = [
  "Habitação",
  "Educação",
  "Saúde",
  "Cultura",
  "Equipamentos públicos",
  "Espaço público",
  "Urbanismo",
  "Paisagismo",
  "Mobilidade",
  "Património",
  "Reabilitação",
];

export default function ProfileSpecialties() {
  const { profile } = useProfile();
  const { isEditing, updateSpecialties } = useEditingProfile();
  const { specialties } = profile;

  const toggleArea = (area: string) => {
    const areas = specialties.areas.includes(area)
      ? specialties.areas.filter((a) => a !== area)
      : [...specialties.areas, area];
    updateSpecialties({ areas });
  };

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <Lightbulb size={20} />
        <div>
          <h2>Especialidades / Áreas de Interesse</h2>
          <p>Seleciona as áreas onde o teu atelier atua ou tem interesse.</p>
        </div>
      </div>

      <div className="profile-card-body">
        {specialties.areas.length === 0 && !isEditing ? (
          <div className="profile-empty-message">Nenhuma especialidade selecionada</div>
        ) : (
          <div className="profile-chip-group">
            {especialidades.map((area) => (
              <button
                key={area}
                className={`profile-chip ${specialties.areas.includes(area) ? "active" : ""}`}
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
