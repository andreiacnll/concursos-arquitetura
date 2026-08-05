"use client";

import type { CompanyProfile } from "./company-types";
import { listToText, textToList } from "./company-types";

type Props = {
  profile: CompanyProfile;
  isEditing: boolean;
  onChange: (next: CompanyProfile) => void;
};

function updateProfile(
  profile: CompanyProfile,
  updater: (draft: CompanyProfile) => void,
): CompanyProfile {
  const draft = JSON.parse(JSON.stringify(profile)) as CompanyProfile;
  updater(draft);
  return draft;
}

function SectionField({
  label,
  value,
  placeholder,
  isEditing,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  placeholder?: string;
  isEditing: boolean;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <div className="profile-field">
      <label>{label}</label>
      {multiline ? (
        <textarea
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          disabled={!isEditing}
          rows={4}
        />
      ) : (
        <input
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          disabled={!isEditing}
        />
      )}
    </div>
  );
}

export default function CompanyInformationSection({
  profile,
  isEditing,
  onChange,
}: Props) {
  const hasEmptyFields =
    !profile.identity.company_name &&
    !profile.identity.description &&
    !profile.identity.location &&
    !profile.identity.website &&
    profile.services.length === 0 &&
    profile.competences.length === 0 &&
    profile.specializations.length === 0 &&
    Object.values(profile.strategy).every((items) => items.length === 0);

  return (
    <section
      style={{
        background: "white",
        border: "1px solid #e7e7e0",
        borderRadius: "18px",
        padding: "24px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "flex-start", marginBottom: "18px" }}>
        <div>
          <h2 style={{ fontSize: "20px", marginBottom: "6px" }}>Informação da empresa</h2>
          <p style={{ color: "#777", margin: 0, fontSize: "14px" }}>
            {isEditing
              ? "Edita os dados base da tua empresa."
              : "Os dados abaixo são mostrados a partir do perfil guardado."}
          </p>
        </div>

        {hasEmptyFields && (
          <span
            style={{
              padding: "6px 10px",
              borderRadius: "999px",
              background: "#f5f1e8",
              color: "#8a6b2b",
              fontSize: "12px",
              whiteSpace: "nowrap",
            }}
          >
            Perfil vazio
          </span>
        )}
      </div>

      <div className="profile-field-row">
        <SectionField
          label="Nome da empresa"
          value={profile.identity.company_name}
          placeholder="Ex.: Atelier Horizonte"
          isEditing={isEditing}
          onChange={(value) =>
            onChange(
              updateProfile(profile, (draft) => {
                draft.identity.company_name = value;
              }),
            )
          }
        />

        <SectionField
          label="Website"
          value={profile.identity.website}
          placeholder="https://..."
          isEditing={isEditing}
          onChange={(value) =>
            onChange(
              updateProfile(profile, (draft) => {
                draft.identity.website = value;
              }),
            )
          }
        />
      </div>

      <SectionField
        label="Identidade"
        value={profile.identity.description}
        placeholder="Descreve a identidade e posicionamento da empresa."
        isEditing={isEditing}
        multiline
        onChange={(value) =>
          onChange(
            updateProfile(profile, (draft) => {
              draft.identity.description = value;
            }),
          )
        }
      />

      <div className="profile-field-row">
        <SectionField
          label="Localização"
          value={profile.identity.location}
          placeholder="Ex.: Lisboa"
          isEditing={isEditing}
          onChange={(value) =>
            onChange(
              updateProfile(profile, (draft) => {
                draft.identity.location = value;
              }),
            )
          }
        />

        <SectionField
          label="Serviços"
          value={listToText(profile.services)}
          placeholder="arquitetura, urbanismo, reabilitação"
          isEditing={isEditing}
          multiline
          onChange={(value) =>
            onChange(
              updateProfile(profile, (draft) => {
                draft.services = textToList(value);
              }),
            )
          }
        />
      </div>

      <SectionField
        label="Competências"
        value={listToText(profile.competences)}
        placeholder="BIM, Revit, coordenação"
        isEditing={isEditing}
        multiline
        onChange={(value) =>
          onChange(
            updateProfile(profile, (draft) => {
              draft.competences = textToList(value);
            }),
          )
        }
      />

      <SectionField
        label="Especializações"
        value={listToText(profile.specializations)}
        placeholder="reabilitação, património, BIM"
        isEditing={isEditing}
        multiline
        onChange={(value) =>
          onChange(
            updateProfile(profile, (draft) => {
              draft.specializations = textToList(value);
            }),
          )
        }
      />

      <div style={{ marginTop: "24px" }}>
        <h3 style={{ fontSize: "16px", marginBottom: "14px" }}>Estratégia</h3>

        <div className="profile-field">
          <label>Áreas prioritárias</label>
          <textarea
            value={listToText(profile.strategy.priority_areas)}
            placeholder="cultura, educação, habitação"
            onChange={(event) =>
              onChange(
                updateProfile(profile, (draft) => {
                  draft.strategy.priority_areas = textToList(event.target.value);
                }),
              )
            }
            disabled={!isEditing}
            rows={3}
          />
        </div>

        <div className="profile-field">
          <label>Áreas secundárias</label>
          <textarea
            value={listToText(profile.strategy.secondary_areas)}
            placeholder="reabilitação, espaço público"
            onChange={(event) =>
              onChange(
                updateProfile(profile, (draft) => {
                  draft.strategy.secondary_areas = textToList(event.target.value);
                }),
              )
            }
            disabled={!isEditing}
            rows={3}
          />
        </div>

        <div className="profile-field">
          <label>Áreas a evitar</label>
          <textarea
            value={listToText(profile.strategy.avoid_areas)}
            placeholder="tipologias ou concursos que não querem perseguir"
            onChange={(event) =>
              onChange(
                updateProfile(profile, (draft) => {
                  draft.strategy.avoid_areas = textToList(event.target.value);
                }),
              )
            }
            disabled={!isEditing}
            rows={3}
          />
        </div>

        <div className="profile-field">
          <label>Objetivos futuros</label>
          <textarea
            value={listToText(profile.strategy.future_goals)}
            placeholder="crescimento, novas tipologias, expansão territorial"
            onChange={(event) =>
              onChange(
                updateProfile(profile, (draft) => {
                  draft.strategy.future_goals = textToList(event.target.value);
                }),
              )
            }
            disabled={!isEditing}
            rows={3}
          />
        </div>
      </div>
    </section>
  );
}
