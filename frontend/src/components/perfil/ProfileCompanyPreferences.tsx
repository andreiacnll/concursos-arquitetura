"use client";

import { useEffect, useState } from "react";
import { Loader2, Pencil, Save, X } from "lucide-react";
import { saveCompanyProfileWithDiagnostics } from "@/lib/company-profile-api";
import {
  listToText,
  normalizeCompanyProfile,
  textToList,
  type CompanyProfile,
} from "@/components/company/company-types";

type Props = {
  profile: CompanyProfile;
  token?: string;
  hasProfile: boolean;
  onSaved: (profile: CompanyProfile) => void;
};

type Draft = {
  typologies: string;
  procedures: string;
  locations: string;
  projectScale: string;
  priorityAreas: string;
  secondaryAreas: string;
  avoidAreas: string;
  futureGoals: string;
};

function draftFromProfile(profile: CompanyProfile): Draft {
  return {
    typologies: listToText(profile.preferences.typologies),
    procedures: listToText(profile.preferences.procedures),
    locations: listToText(profile.preferences.locations),
    projectScale: listToText(profile.preferences.project_scale),
    priorityAreas: listToText(profile.strategy.priority_areas),
    secondaryAreas: listToText(profile.strategy.secondary_areas),
    avoidAreas: listToText(profile.strategy.avoid_areas),
    futureGoals: listToText(profile.strategy.future_goals),
  };
}

function Field({
  id,
  label,
  value,
  editing,
  onChange,
}: {
  id: keyof Draft;
  label: string;
  value: string;
  editing: boolean;
  onChange: (id: keyof Draft, value: string) => void;
}) {
  return (
    <label className="profile-field">
      <span>{label}</span>
      {editing ? (
        <textarea
          value={value}
          rows={3}
          onChange={(event) => onChange(id, event.target.value)}
          placeholder="Separar por vírgulas ou linhas"
        />
      ) : (
        <div className="profile-value">
          {value.trim() || "Sem informação guardada."}
        </div>
      )}
    </label>
  );
}

export default function ProfileCompanyPreferences({
  profile,
  token,
  hasProfile,
  onSaved,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => draftFromProfile(profile));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDraft(draftFromProfile(profile));
    }
  }, [editing, profile]);

  function updateDraft(id: keyof Draft, value: string) {
    setDraft((current) => ({ ...current, [id]: value }));
  }

  async function handleSave() {
    if (!token) {
      setError("A sessão terminou. Volta a iniciar sessão.");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const next = normalizeCompanyProfile({
        ...profile,
        preferences: {
          typologies: textToList(draft.typologies),
          procedures: textToList(draft.procedures),
          locations: textToList(draft.locations),
          project_scale: textToList(draft.projectScale),
        },
        strategy: {
          ...profile.strategy,
          priority_areas: textToList(draft.priorityAreas),
          secondary_areas: textToList(draft.secondaryAreas),
          avoid_areas: textToList(draft.avoidAreas),
          future_goals: textToList(draft.futureGoals),
        },
      });
      const saved = await saveCompanyProfileWithDiagnostics(
        token,
        next,
        hasProfile,
      );
      onSaved(saved);
      setEditing(false);
      setSuccess("Preferências guardadas com sucesso.");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Não foi possível guardar as preferências.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <div>
          <h2>Preferências de concursos</h2>
          <p>Preferências empresariais usadas para recomendações.</p>
        </div>
        <div className="profile-card-actions">
          {editing ? (
            <>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setEditing(false);
                  setError(null);
                  setSuccess(null);
                  setDraft(draftFromProfile(profile));
                }}
                disabled={saving}
              >
                <X size={15} />
                Cancelar
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? <Loader2 size={15} className="spin" /> : <Save size={15} />}
                Guardar
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setEditing(true);
                setError(null);
                setSuccess(null);
              }}
            >
              <Pencil size={15} />
              Editar
            </button>
          )}
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-field-row">
          <Field
            id="typologies"
            label="Tipologias preferidas"
            value={draft.typologies}
            editing={editing}
            onChange={updateDraft}
          />
          <Field
            id="procedures"
            label="Procedimentos preferidos"
            value={draft.procedures}
            editing={editing}
            onChange={updateDraft}
          />
        </div>
        <div className="profile-field-row">
          <Field
            id="locations"
            label="Localizações preferidas"
            value={draft.locations}
            editing={editing}
            onChange={updateDraft}
          />
          <Field
            id="projectScale"
            label="Escala dos projetos"
            value={draft.projectScale}
            editing={editing}
            onChange={updateDraft}
          />
        </div>
        <div className="profile-field-row">
          <Field
            id="priorityAreas"
            label="Áreas prioritárias"
            value={draft.priorityAreas}
            editing={editing}
            onChange={updateDraft}
          />
          <Field
            id="secondaryAreas"
            label="Áreas secundárias"
            value={draft.secondaryAreas}
            editing={editing}
            onChange={updateDraft}
          />
        </div>
        <div className="profile-field-row">
          <Field
            id="avoidAreas"
            label="Áreas a evitar"
            value={draft.avoidAreas}
            editing={editing}
            onChange={updateDraft}
          />
          <Field
            id="futureGoals"
            label="Objetivos futuros"
            value={draft.futureGoals}
            editing={editing}
            onChange={updateDraft}
          />
        </div>

        {error && <div className="profile-form-message error">{error}</div>}
        {success && <div className="profile-form-message success">{success}</div>}
      </div>
    </div>
  );
}
