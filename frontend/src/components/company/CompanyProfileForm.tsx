"use client";

import { Building2, Loader2, Save, PencilLine, X } from "lucide-react";
import CompanyInformationSection from "./CompanyInformationSection";
import CompanyExperienceCards from "./CompanyExperienceCards";
import CompanyKnowledgeSection from "./CompanyKnowledgeSection";
import {
  CompanyProfile,
  isCompanyProfileEmpty,
} from "./company-types";

type Props = {
  profile: CompanyProfile;
  isEditing: boolean;
  isNewProfile: boolean;
  saving: boolean;
  loading: boolean;
  error: string | null;
  success: string | null;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onChange: (next: CompanyProfile) => void;
};

export default function CompanyProfileForm({
  profile,
  isEditing,
  isNewProfile,
  saving,
  loading,
  error,
  success,
  onEdit,
  onCancel,
  onSave,
  onChange,
}: Props) {
  const emptyProfile = isCompanyProfileEmpty(profile);

  return (
    <div style={{ display: "grid", gap: "20px" }}>
      <section
        style={{
          background: "white",
          border: "1px solid #e7e7e0",
          borderRadius: "18px",
          padding: "24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", gap: "14px", alignItems: "flex-start" }}>
          <div
            style={{
              width: "42px",
              height: "42px",
              borderRadius: "12px",
              background: "#f4f7f0",
              color: "#607b43",
              display: "grid",
              placeItems: "center",
              flex: "0 0 auto",
            }}
          >
            <Building2 size={20} />
          </div>

          <div>
            <h1 style={{ fontSize: "28px", marginBottom: "6px" }}>
              Minha Empresa
            </h1>
            <p style={{ color: "#777", margin: 0 }}>
              Garante que o perfil da tua empresa está pronto para o motor de
              inteligência e para futuras recomendações.
            </p>

            {(emptyProfile || isNewProfile) && !loading && (
              <p
                style={{
                  marginTop: "10px",
                  color: "#8a6b2b",
                  background: "#f5f1e8",
                  borderRadius: "999px",
                  display: "inline-flex",
                  padding: "6px 10px",
                  fontSize: "12px",
                }}
              >
                Perfil vazio
              </p>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          {!isEditing ? (
            <button className="btn-primary" type="button" onClick={onEdit}>
              <PencilLine size={16} />
              {emptyProfile ? "Criar perfil empresarial" : "Editar perfil"}
            </button>
          ) : (
            <>
              <button
                className="btn-primary"
                type="button"
                onClick={onSave}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    A guardar...
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    Guardar alterações
                  </>
                )}
              </button>
              <button
                className="btn-secondary"
                type="button"
                onClick={onCancel}
                disabled={saving}
              >
                <X size={16} />
                Cancelar
              </button>
            </>
          )}
        </div>
      </section>

      {success && (
        <div
          style={{
            padding: "14px 16px",
            borderRadius: "14px",
            background: "#f4faef",
            border: "1px solid #dce8c9",
            color: "#4f6f2d",
          }}
          role="status"
        >
          {success}
        </div>
      )}

      {error && (
        <div
          style={{
            padding: "14px 16px",
            borderRadius: "14px",
            background: "#fff5f5",
            border: "1px solid #f0cccc",
            color: "#9f3a3a",
          }}
          role="alert"
        >
          {error}
        </div>
      )}

      <CompanyInformationSection
        profile={profile}
        isEditing={isEditing}
        onChange={onChange}
      />

      <CompanyExperienceCards profile={profile} />

      <CompanyKnowledgeSection profile={profile} />
    </div>
  );
}
