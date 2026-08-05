"use client";

import { useState, Suspense } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import PublicLayout from "@/components/layout/PublicLayout";
import { Eye, EyeOff, LogIn } from "lucide-react";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberSession, setRememberSession] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { signIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/";
  const [error, setError] = useState<string | null>(
    searchParams.get("error") === "confirmation_failed"
      ? "Não foi possível confirmar o email. O link pode ter expirado."
      : null,
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;

    setError(null);
    setLoading(true);

    const { error, session } = await signIn(
      email.trim(),
      password,
      rememberSession,
    );
    if (error) {
      setError(error);
      setLoading(false);
      return;
    }

    if (!session) {
      setError(
        "Login concluído sem sessão ativa. Verifica a configuração Supabase.",
      );
      setLoading(false);
      return;
    }

    router.replace(
      redirect.startsWith("/") && !redirect.startsWith("//")
        ? redirect
        : "/",
    );
    router.refresh();
  };

  return (
    <PublicLayout>
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-card-header">
            <LogIn size={24} />
            <h1>Entrar</h1>
            <p>Acede à tua conta do Portal Concursos</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="auth-error">{error}</div>}

            <div className="profile-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="teu@email.pt"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="profile-field">
              <label>Password</label>
              <div className="auth-password-control">
                <input
                  type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  aria-label={
                    showPassword ? "Ocultar password" : "Mostrar password"
                  }
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <label className="check-row">
              <input
                type="checkbox"
                checked={rememberSession}
                onChange={(event) =>
                  setRememberSession(event.target.checked)
                }
              />
              <span>Manter sessão iniciada</span>
            </label>

            <button
              type="submit"
              className="auth-submit"
              disabled={loading}
            >
              {loading ? "A entrar..." : "Entrar"}
            </button>
          </form>

          <p className="auth-footer">
            Ainda não tens conta?{" "}
            <Link href="/auth/register">Criar conta</Link>
          </p>
        </div>
      </div>
    </PublicLayout>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
