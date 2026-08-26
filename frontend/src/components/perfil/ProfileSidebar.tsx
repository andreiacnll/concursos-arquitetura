"use client";

import {
  BarChart3,
  Bell,
  BriefcaseBusiness,
  Building2,
  Database,
  FileText,
  Lightbulb,
  SlidersHorizontal,
  UserRound,
  Users,
} from "lucide-react";

const profileSections = [
  { id: "personal", label: "Dados pessoais", icon: UserRound },
  { id: "account", label: "Conta e segurança", icon: SlidersHorizontal },
  { id: "notifications", label: "Notificações pessoais", icon: Bell },
];

const companySections = [
  { id: "company-identity", label: "Identidade", icon: Building2 },
  { id: "team", label: "Equipa", icon: Users },
  { id: "services", label: "Serviços", icon: BriefcaseBusiness },
  { id: "specialties", label: "Especialidades", icon: Lightbulb },
  { id: "experience", label: "Experiência", icon: BarChart3 },
  { id: "preferences", label: "Preferências de concursos", icon: SlidersHorizontal },
  { id: "knowledge", label: "Conhecimento IA", icon: Database },
  { id: "sources", label: "Fontes", icon: FileText },
];

interface ProfileSidebarProps {
  active: string;
  onSelect: (id: string) => void;
  onboardingComplete: boolean;
}

export default function ProfileSidebar({
  active,
  onSelect,
  onboardingComplete,
}: ProfileSidebarProps) {
  return (
    <aside className="profile-sidebar">
      <div className="profile-sidebar-header">
        <div className="profile-sidebar-icon">
          <UserRound size={22} />
        </div>
        <div>
          <strong>Perfil</strong>
          <span>{onboardingComplete ? "Área pessoal" : "Área pessoal"}</span>
        </div>
      </div>

      <nav className="profile-sidebar-nav" aria-label="Navegação do perfil">
        <span className="profile-sidebar-group-label">PERFIL</span>
        {profileSections.map((sec) => {
          const Icon = sec.icon;
          const isActive = active === sec.id;
          return (
            <button
              key={sec.id}
              type="button"
              className={`profile-sidebar-link ${isActive ? "active" : ""}`}
              onClick={() => onSelect(sec.id)}
            >
              <Icon size={17} />
              <span>{sec.label}</span>
            </button>
          );
        })}

        <span className="profile-sidebar-group-label">EMPRESA</span>
        {companySections.map((sec) => {
          const Icon = sec.icon;
          const isActive = active === sec.id;
          return (
            <button
              key={sec.id}
              type="button"
              className={`profile-sidebar-link ${isActive ? "active" : ""}`}
              onClick={() => onSelect(sec.id)}
            >
              <Icon size={17} />
              <span>{sec.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
