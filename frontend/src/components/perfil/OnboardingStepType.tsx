"use client";

import { User, Building2, Briefcase } from "lucide-react";

interface Props {
  selected: string | null;
  onSelect: (type: string) => void;
}

const types = [
  {
    value: "individual",
    icon: User,
    title: "Pessoa individual",
    desc: "Arquiteto(a) independente",
  },
  {
    value: "atelier",
    icon: Building2,
    title: "Atelier / Escritório",
    desc: "Escritório de arquitetura constituído",
  },
  {
    value: "empresa",
    icon: Briefcase,
    title: "Empresa / Equipa",
    desc: "Equipa multidisciplinar",
  },
];

export default function OnboardingStepType({ selected, onSelect }: Props) {
  return (
    <div className="onboarding-step">
      <h2>Que tipo de utilizador és?</h2>
      <p>Escolhe a opção que melhor descreve a tua situação.</p>

      <div className="onboarding-type-grid">
        {types.map((t) => {
          const Icon = t.icon;
          const isActive = selected === t.value;
          return (
            <button
              key={t.value}
              className={`onboarding-type-card ${isActive ? "active" : ""}`}
              onClick={() => onSelect(t.value)}
            >
              <Icon size={28} />
              <strong>{t.title}</strong>
              <span>{t.desc}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}