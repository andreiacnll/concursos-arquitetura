"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { Building2, MapPin, Globe, Mail, FileText, Users, Calendar } from "lucide-react";

export default function ProfileIdentity() {
  const { profile } = useProfile();
  const { isEditing, updateAtelier: updateEditingAtelier } = useEditingProfile();
  const a = profile.atelier;

  const handleChange = (field: string, value: string) => {
    updateEditingAtelier({ [field]: value });
  };

  const renderField = (label: string, icon: React.ReactNode, field: keyof typeof a, placeholder: string, type = "text") => {
    const value = a[field] as string;
    const isEmpty = !value || value.trim() === "";

    if (isEditing) {
      return (
        <div className="profile-field">
          <label>
            {icon}
            {label}
          </label>
          <input
            type={type}
            placeholder={placeholder}
            value={value}
            onChange={(e) => handleChange(field, e.target.value)}
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
        <Building2 size={20} />
        <div>
          <h2>Identidade do Atelier</h2>
          <p>Informação principal do teu escritório de arquitetura.</p>
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-field-row">
          {renderField("Nome do Atelier", <Building2 size={15} />, "nome", "Ex.: Atelier Central")}
          {renderField("Localização", <MapPin size={15} />, "localizacao", "Ex.: Lisboa, Portugal")}
        </div>

        <div className="profile-field-row">
          {renderField("Website", <Globe size={15} />, "website", "https://atelier.pt", "url")}
          {renderField("Email profissional", <Mail size={15} />, "email", "geral@atelier.pt", "email")}
        </div>

        <div className="profile-field-row">
          {renderField("Número de elementos", <Users size={15} />, "numElementos", "Ex.: 8")}
          {renderField("Ano de fundação", <Calendar size={15} />, "anoFundacao", "Ex.: 2015")}
        </div>

        <div className="profile-field">
          <label>
            <FileText size={15} />
            Descrição curta
          </label>
          {isEditing ? (
            <textarea
              placeholder="Descreve o teu atelier em poucas linhas..."
              rows={3}
              value={a.descricao}
              onChange={(e) => handleChange("descricao", e.target.value)}
            />
          ) : (
            <div className={`profile-value ${!a.descricao ? "profile-empty-field" : ""}`}>
              {a.descricao || "Não definido"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
