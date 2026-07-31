"use client";

import Link from "next/link";
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
  { id: "identity", label: "Identidade", icon: UserRound },
  { id: "notifications", label: "Notificacoes pessoais", icon: Bell },
];

const companySections = [
  { id: "company-identity", label: "Identidade", icon: Building2, href: "/empresa" },
  { id: "team", label: "Equipa", icon: Users },
  { id: "services", label: "Servicos", icon: BriefcaseBusiness, href: "/empresa" },
  { id: "specialties", label: "Especialidades", icon: Lightbulb },
  { id: "experience", label: "Experiencia", icon: BarChart3 },
  { id: "preferences", label: "Preferencias de concursos", icon: SlidersHorizontal },
  { id: "knowledge", label: "Conhecimento IA", icon: Database, href: "/empresa" },
  { id: "sources", label: "Fontes", icon: FileText, href: "/empresa" },
];

interface ProfileSidebarProps {
  active: string;
  onSelect: (id: string) => void;
  onboardingComplete: boolean;
}

export default function ProfileSidebar({ active, onSelect, onboardingComplete }: ProfileSidebarProps) {
  return (
    <aside className="profile-sidebar">
      <div className="profile-sidebar-header">
        <div className="profile-sidebar-icon">
          <UserRound size={22} />
        </div>
        <div>
          <strong>Perfil</strong>
          <span>{onboardingComplete ? "Empresa configurada" : "Empresa por configurar"}</span>
        </div>
      </div>

      <nav className="profile-sidebar-nav" aria-label="Navegacao do perfil">
        <span className="profile-sidebar-group-label">PERFIL</span>
        {profileSections.map((sec) => {
          const Icon = sec.icon;
          const isActive = active === sec.id;
          return (
            <button
              key={sec.id}
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
          if (sec.href) {
            return (
              <Link
                key={sec.id}
                className="profile-sidebar-link"
                href={sec.href}
              >
                <Icon size={17} />
                <span>{sec.label}</span>
              </Link>
            );
          }
          return (
            <button
              key={sec.id}
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
