"use client";

import { useProfile } from "@/context/ProfileContext";
import { Building2, MapPin, Globe, Mail, FileText, Users, Calendar } from "lucide-react";

export default function OnboardingStepAtelier() {
  const { profile, updateAtelier } = useProfile();
  const a = profile.atelier;

  return (
    <div className="onboarding-step">
      <h2>Dados do Atelier</h2>
      <p>Preenche a informação principal do teu escritório.</p>

      <div className="onboarding-form">
        <div className="profile-field-row">
          <div className="profile-field">
            <label>
              <Building2 size={15} />
              Nome do Atelier
            </label>
            <input
              type="text"
              placeholder="Ex.: Atelier Central"
              value={a.nome}
              onChange={(e) => updateAtelier({ nome: e.target.value })}
            />
          </div>

          <div className="profile-field">
            <label>
              <MapPin size={15} />
              Localização principal
            </label>
            <input
              type="text"
              placeholder="Ex.: Lisboa"
              value={a.localizacao}
              onChange={(e) => updateAtelier({ localizacao: e.target.value })}
            />
          </div>
        </div>

        <div className="profile-field-row">
          <div className="profile-field">
            <label>
              <Globe size={15} />
              Website
            </label>
            <input
              type="url"
              placeholder="https://atelier.pt"
              value={a.website}
              onChange={(e) => updateAtelier({ website: e.target.value })}
            />
          </div>

          <div className="profile-field">
            <label>
              <Mail size={15} />
              Email profissional
            </label>
            <input
              type="email"
              placeholder="geral@atelier.pt"
              value={a.email}
              onChange={(e) => updateAtelier({ email: e.target.value })}
            />
          </div>
        </div>

        <div className="profile-field-row">
          <div className="profile-field">
            <label>
              <Users size={15} />
              Número de elementos
            </label>
            <input
              type="text"
              placeholder="Ex.: 8"
              value={a.numElementos}
              onChange={(e) => updateAtelier({ numElementos: e.target.value })}
            />
          </div>

          <div className="profile-field">
            <label>
              <Calendar size={15} />
              Ano de fundação
            </label>
            <input
              type="text"
              placeholder="Ex.: 2015"
              value={a.anoFundacao}
              onChange={(e) => updateAtelier({ anoFundacao: e.target.value })}
            />
          </div>
        </div>

        <div className="profile-field">
          <label>
            <FileText size={15} />
            Descrição curta
          </label>
          <textarea
            placeholder="Descreve o teu atelier em poucas linhas..."
            rows={3}
            value={a.descricao}
            onChange={(e) => updateAtelier({ descricao: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}