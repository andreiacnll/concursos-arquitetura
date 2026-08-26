"use client";

import { FormEvent, useState } from "react";
import { Eye, EyeOff, Loader2, LogOut, Mail, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { createClient } from "@/lib/supabase/client";

function classifyPasswordError(message: string) {
  const normalized = message.toLowerCase();
  if (
    normalized.includes("invalid login credentials") ||
    normalized.includes("invalid credentials")
  ) {
    return "A password atual não está correta.";
  }
  if (normalized.includes("weak") || normalized.includes("password")) {
    return `A nova password foi recusada pelo Supabase: ${message}`;
  }
  if (normalized.includes("failed to fetch") || normalized.includes("network")) {
    return "Erro de rede ao comunicar com o Supabase.";
  }
  return message || "Não foi possível alterar a palavra-passe.";
}

export default function ProfileAccountSecurity() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    const email = user?.email;
    if (!email) {
      setError("Não foi possível confirmar o email da conta atual.");
      return;
    }
    if (!currentPassword) {
      setError("Introduz a password atual.");
      return;
    }
    if (newPassword.length < 8) {
      setError("A nova password deve ter pelo menos 8 caracteres.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("A confirmação não coincide com a nova password.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("A nova password deve ser diferente da password atual.");
      return;
    }

    setLoading(true);
    try {
      const supabase = createClient();
      const reauth = await supabase.auth.signInWithPassword({
        email,
        password: currentPassword,
      });

      if (reauth.error) {
        setError(classifyPasswordError(reauth.error.message));
        return;
      }

      const { error: updateError } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (updateError) {
        setError(classifyPasswordError(updateError.message));
        return;
      }

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Palavra-passe alterada com sucesso.");
      router.refresh();
    } catch (caught) {
      setError(
        classifyPasswordError(
          caught instanceof Error ? caught.message : "Erro inesperado.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  const passwordType = showPasswords ? "text" : "password";

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <ShieldCheck size={20} />
        <div>
          <h2>Conta e segurança</h2>
          <p>Definições suportadas pela autenticação atual.</p>
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-field-row">
          <div className="profile-field">
            <label>
              <Mail size={15} />
              Email da conta
            </label>
            <div className="profile-value">{user?.email ?? "Não definido"}</div>
          </div>
          <div className="profile-field">
            <label>Verificação do email</label>
            <div className="profile-value">
              {user?.email_confirmed_at ? "Verificado" : "Por confirmar"}
            </div>
          </div>
        </div>

        <form className="profile-password-form" onSubmit={handlePasswordSubmit}>
          <div className="profile-card-header compact">
            <div>
              <h3>Alterar palavra-passe</h3>
              <p>Confirma a password atual antes de definir uma nova.</p>
            </div>
            <button
              type="button"
              className="profile-icon-button"
              aria-label={
                showPasswords
                  ? "Ocultar passwords"
                  : "Mostrar passwords"
              }
              onClick={() => setShowPasswords((value) => !value)}
            >
              {showPasswords ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>

          <div className="profile-field-row">
            <label className="profile-field">
              <span>Password atual</span>
              <input
                type={passwordType}
                value={currentPassword}
                autoComplete="current-password"
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>
            <label className="profile-field">
              <span>Nova password</span>
              <input
                type={passwordType}
                value={newPassword}
                autoComplete="new-password"
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </label>
            <label className="profile-field">
              <span>Confirmar password</span>
              <input
                type={passwordType}
                value={confirmPassword}
                autoComplete="new-password"
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </label>
          </div>

          {error && <div className="profile-form-message error">{error}</div>}
          {success && (
            <div className="profile-form-message success">{success}</div>
          )}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? <Loader2 size={16} className="spin" /> : null}
            {loading ? "A guardar..." : "Guardar nova password"}
          </button>
        </form>

        <button
          type="button"
          className="btn-secondary"
          onClick={async () => {
            await signOut();
            router.replace("/");
            router.refresh();
          }}
        >
          <LogOut size={16} />
          Terminar sessão
        </button>
      </div>
    </div>
  );
}
