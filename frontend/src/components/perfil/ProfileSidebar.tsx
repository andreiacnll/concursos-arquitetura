"use client";

import { Building2, Users, Lightbulb, SlidersHorizontal, BarChart3, Bell } from "lucide-react";

const sections = [
  { id: "identity", label: "Identidade", icon: Building2 },
  { id: "team", label: "Equipa", icon: Users },
  { id: "specialties", label: "Especialidades", icon: Lightbulb },
  { id: "preferences", label: "Preferências de pesquisa", icon: SlidersHorizontal },
  { id: "experience", label: "Experiência", icon: BarChart3 },
  { id: "notifications", label: "Notificações", icon: Bell },
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
          <Building2 size={22} />
        </div>
        <div>
          <strong>Perfil do Atelier</strong>
          <span>{onboardingComplete ? "Configurado" : "Por configurar"}</span>
        </div>
      </div>

      <nav className="profile-sidebar-nav">
        {sections.map((sec) => {
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
      </nav>
    </aside>
  );
}