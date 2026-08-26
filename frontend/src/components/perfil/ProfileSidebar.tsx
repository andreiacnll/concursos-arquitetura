"use client";

import { BriefcaseBusiness, UserRound } from "lucide-react";

const profileSections = [{ id: "profile", label: "Perfil", icon: UserRound }];
const companySections = [{ id: "company", label: "Empresa", icon: BriefcaseBusiness }];

interface ProfileSidebarProps {
  active: string;
  onSelect: (id: string) => void;
}

export default function ProfileSidebar({ active, onSelect }: ProfileSidebarProps) {
  return (
    <aside className="profile-sidebar">
      <div className="profile-sidebar-header">
        <div className="profile-sidebar-icon">
          <UserRound size={22} />
        </div>
        <div>
          <strong>Perfil</strong>
          <span>Área pessoal</span>
        </div>
      </div>

      <nav className="profile-sidebar-nav" aria-label="Navegação do perfil">
        <span className="profile-sidebar-group-label">PERFIL</span>
        {profileSections.map((sec) => {
          const Icon = sec.icon;
          return (
            <button key={sec.id} type="button" className={`profile-sidebar-link ${active === sec.id ? "active" : ""}`} onClick={() => onSelect(sec.id)}>
              <Icon size={17} />
              <span>{sec.label}</span>
            </button>
          );
        })}

        <span className="profile-sidebar-group-label">EMPRESA</span>
        {companySections.map((sec) => {
          const Icon = sec.icon;
          return (
            <button key={sec.id} type="button" className={`profile-sidebar-link ${active === sec.id ? "active" : ""}`} onClick={() => onSelect(sec.id)}>
              <Icon size={17} />
              <span>{sec.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}