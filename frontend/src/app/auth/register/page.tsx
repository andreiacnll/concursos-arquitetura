"use client";

import { useState, Suspense } from "react";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import PublicLayout from "@/components/layout/PublicLayout";
import { UserPlus } from "lucide-react";

function RegisterForm() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const { signUp } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { error } = await signUp(email, password, { nome });
    if (error) {
      setError(error);
      setLoading(false);
    } else {
      setSuccess(true);
    }
  };

  if (success) {
    return (
      <PublicLayout>
        <div className="auth-page">
          <div className="auth-card">
            <div className="auth-card-header">
              <UserPlus size={24} />
              <h1>Conta criada</h1>
              <p>
                Verifica o teu email <strong>{email}</strong> para confirmares o
                registo.
              </p>
            </div>
            <p className="auth-footer">
              <Link href="/auth/login">Ir para o login</Link>
            </p>
          </div>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <div className="auth-page">
        <div className="auth-card">
          <div className="auth-card-header">
            <UserPlus size={24} />
            <h1>Criar conta</h1>
            <p>Regista-te no Portal Concursos de Arquitetura</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {error && <div className="auth-error">{error}</div>}

            <div className="profile-field">
              <label>Nome</label>
              <input
                type="text"
                placeholder="O teu nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="profile-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="teu@email.pt"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="profile-field">
              <label>Password</label>
              <input
                type="password"
                placeholder="Mínimo 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? "A criar conta..." : "Criar conta"}
            </button>
          </form>

          <p className="auth-footer">
            Já tens conta? <Link href="/auth/login">Entrar</Link>
          </p>
        </div>
      </div>
    </PublicLayout>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}