"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { SlidersHorizontal, MapPin, FileText, DollarSign, Layers } from "lucide-react";

const procedimentos = [
  "Concurso público",
  "Concurso de conceção",
  "Consulta prévia",
  "Ajuste direto",
];

const servicos = [
  "Projeto de arquitetura",
  "Projeto de execução",
  "Fiscalização",
  "Estudos",
  "Planeamento",
];

const escalas = [
  { value: "pequeno", label: "Pequena escala" },
  { value: "medio", label: "Média escala" },
  { value: "grande", label: "Grande escala" },
];

const intervalosPreco = [
  { value: "ate-250k", label: "< 250.000€" },
  { value: "250k-1m", label: "250.000€ – 1M€" },
  { value: "acima-1m", label: "> 1M€" },
];

const categorias = [
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

export default function ProfilePreferences() {
  const { profile } = useProfile();
  const { isEditing, updatePreferences, editingProfile } = useEditingProfile();
  const preferences = isEditing ? editingProfile.preferences : profile.preferences;

  const toggleItem = (key: "procedimentos" | "servicos" | "categorias", value: string) => {
    const arr = preferences[key];
    const updated = arr.includes(value)
      ? arr.filter((v: string) => v !== value)
      : [...arr, value];
    updatePreferences({ [key]: updated });
  };

  const hasAnySelection = preferences.procedimentos.length > 0 || 
                          preferences.servicos.length > 0 || 
                          preferences.categorias.length > 0 ||
                          preferences.escala ||
                          preferences.intervaloPreco;

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <SlidersHorizontal size={20} />
        <div>
          <h2>Preferências de Pesquisa</h2>
          <p>Estes dados vão alimentar automaticamente a tua pesquisa de concursos.</p>
        </div>
      </div>

      <div className="profile-card-body">
        {/* Localização / Âmbito */}
        <div className="profile-field">
          <label>
            <MapPin size={15} />
            Âmbito geográfico
          </label>
          <div className="profile-chip-group">
            {[
              { value: "nacional", label: "Nacional" },
              { value: "distritos", label: "Distritos" },
              { value: "municipios", label: "Municípios" },
            ].map((opt) => (
              <button
                key={opt.value}
                className={`profile-chip ${preferences.ambito === opt.value ? "active" : ""}`}
                onClick={() => updatePreferences({ ambito: opt.value })}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tipo de procedimento */}
        <div className="profile-field" style={{ marginTop: 28 }}>
          <label>
            <FileText size={15} />
            Tipo de procedimento
          </label>
          {preferences.procedimentos.length === 0 && !isEditing ? (
            <div className="profile-empty-message">Nenhum procedimento selecionado</div>
          ) : (
            <div className="profile-chip-group">
              {procedimentos.map((p) => (
                <button
                  key={p}
                  className={`profile-chip ${preferences.procedimentos.includes(p) ? "active" : ""}`}
                  onClick={() => toggleItem("procedimentos", p)}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Tipo de serviço */}
        <div className="profile-field" style={{ marginTop: 28 }}>
          <label>
            <Layers size={15} />
            Tipo de serviço
          </label>
          {preferences.servicos.length === 0 && !isEditing ? (
            <div className="profile-empty-message">Nenhum serviço selecionado</div>
          ) : (
            <div className="profile-chip-group">
              {servicos.map((s) => (
                <button
                  key={s}
                  className={`profile-chip ${preferences.servicos.includes(s) ? "active" : ""}`}
                  onClick={() => toggleItem("servicos", s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Escala / Preço */}
        <div className="profile-field" style={{ marginTop: 28 }}>
          <label>
            <DollarSign size={15} />
            Escala / Preço
          </label>
          <div className="profile-chip-group">
            {escalas.map((e) => (
              <button
                key={e.value}
                className={`profile-chip ${preferences.escala === e.value ? "active" : ""}`}
                onClick={() => updatePreferences({ escala: e.value })}
              >
                {e.label}
              </button>
            ))}
          </div>
        </div>

        <div className="profile-field" style={{ marginTop: 20 }}>
          <label>Intervalo de preço</label>
          <div className="profile-chip-group">
            {intervalosPreco.map((i) => (
              <button
                key={i.value}
                className={`profile-chip ${preferences.intervaloPreco === i.value ? "active" : ""}`}
                onClick={() => updatePreferences({ intervaloPreco: i.value })}
              >
                {i.label}
              </button>
            ))}
          </div>
        </div>

        {/* Categorias preferidas */}
        <div className="profile-field" style={{ marginTop: 28 }}>
          <label>Categorias preferidas</label>
          {preferences.categorias.length === 0 && !isEditing ? (
            <div className="profile-empty-message">Nenhuma categoria selecionada</div>
          ) : (
            <div className="profile-chip-group">
              {categorias.map((c) => (
                <button
                  key={c}
                  className={`profile-chip ${preferences.categorias.includes(c) ? "active" : ""}`}
                  onClick={() => toggleItem("categorias", c)}
                >
                  {c}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
