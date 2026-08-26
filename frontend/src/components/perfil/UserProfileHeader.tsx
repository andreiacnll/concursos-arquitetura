"use client";

import { Building2, Mail, UserRound } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

type Props = {
  companyName?: string;
  companyRole?: string;
};

function displayName(email?: string, metadata?: Record<string, unknown>) {
  const candidate = String(
    metadata?.nome ?? metadata?.full_name ?? metadata?.name ?? "",
  ).trim();
  if (candidate) return candidate;
  return email?.split("@")[0] || "Utilizador";
}

export default function UserProfileHeader({ companyName, companyRole }: Props) {
  const { user } = useAuth();
  const name = displayName(user?.email, user?.user_metadata);
  const role = String(
    user?.user_metadata?.cargo ??
      user?.user_metadata?.funcao ??
      user?.user_metadata?.role ??
      "",
  ).trim();

  return (
    <section className="user-profile-header">
      <div className="user-profile-avatar">
        <UserRound size={28} />
      </div>
      <div className="user-profile-main">
        <h1>{name}</h1>
        {role && <p>{role}</p>}
        <div className="user-profile-meta">
          <span>
            <Mail size={15} />
            {user?.email ?? "Email não definido"}
          </span>
          <span>
            <Building2 size={15} />
            {companyName || "Sem empresa associada"}
          </span>
          <span>{companyRole || "Papel não definido"}</span>
        </div>
      </div>
    </section>
  );
}
