"use client";

import { Mail, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

function valueOrEmpty(value: string | null | undefined) {
  const text = String(value ?? "").trim();
  return text || "Não definido";
}

export default function ProfileIdentity() {
  const { user } = useAuth();
  const metadata = user?.user_metadata ?? {};
  const metadataName = valueOrEmpty(metadata.nome as string | undefined);
  const fullName =
    metadataName !== "Não definido"
      ? metadataName
      : valueOrEmpty(metadata.full_name as string | undefined);
  const role = valueOrEmpty(
    (metadata.role as string | undefined) ??
      (metadata.cargo as string | undefined) ??
      (metadata.funcao as string | undefined),
  );
  const phone = valueOrEmpty(
    (metadata.phone as string | undefined) ??
      (metadata.telefone as string | undefined),
  );
  const emailConfirmed = Boolean(user?.email_confirmed_at);

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <UserRound size={20} />
        <div>
          <h2>Dados pessoais</h2>
          <p>Informação da pessoa autenticada nesta conta.</p>
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-field-row">
          <div className="profile-field">
            <label>
              <UserRound size={15} />
              Nome
            </label>
            <div className="profile-value">{fullName}</div>
          </div>

          <div className="profile-field">
            <label>
              <Mail size={15} />
              Email
            </label>
            <div className="profile-value">{user?.email ?? "Não definido"}</div>
          </div>
        </div>

        <div className="profile-field-row">
          <div className="profile-field">
            <label>Cargo ou função</label>
            <div className="profile-value">{role}</div>
          </div>

          <div className="profile-field">
            <label>Telefone</label>
            <div className="profile-value">{phone}</div>
          </div>
        </div>

        <div className="profile-field">
          <label>
            <ShieldCheck size={15} />
            Estado da conta
          </label>
          <div className="profile-value">
            {emailConfirmed ? "Email verificado" : "Email por confirmar"}
          </div>
        </div>
      </div>
    </div>
  );
}
