"use client";

import { useEffect, useMemo, useState } from "react";
import { Bell, Loader2, Sparkles } from "lucide-react";
import AlertCard, { Alerta } from "./AlertCard";
import "./alerts.css";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";

type Subscricao = {
  concurso_id: number;
  titulo: string;
  entidade?: string | null;
  ativo: boolean | number;
  origem?: string | null;
  e_favorito?: boolean | number;
  tem_analise?: boolean | number;
};

type Tab = "todos" | "novidades" | "datas" | "relevantes";

const tabs: Array<{ id: Tab; label: string }> = [
  { id: "todos", label: "Todos" },
  { id: "novidades", label: "Novidades do concurso" },
  { id: "datas", label: "Datas" },
  { id: "relevantes", label: "Com impacto na análise" },
];

function isData(tipo: string) {
  return tipo === "prazo" || tipo === "alteracao_prazo";
}

export default function AlertsDashboard() {
  const { session } = useAuth();
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [subscricoes, setSubscricoes] = useState<Subscricao[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("todos");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [creatingFor, setCreatingFor] = useState<number | null>(null);
  const [referenciaTemporal] = useState(() => Date.now());

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    fetch(`${API_URL}/alertas`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Não foi possível carregar os alertas.");
        }
        return response.json();
      })
      .then((dados) => {
        setAlertas(dados.alertas ?? []);
        setSubscricoes(dados.subscricoes ?? []);
        setError(null);
      })
      .catch((erro) => {
        setError(
          erro instanceof Error
            ? erro.message
            : "Não foi possível carregar os alertas.",
        );
      })
      .finally(() => setLoading(false));
  }, [session?.access_token]);

  const filtrados = useMemo(() => {
    if (activeTab === "novidades") {
      return alertas.filter((alerta) => !isData(alerta.tipo));
    }
    if (activeTab === "datas") {
      return alertas.filter((alerta) => isData(alerta.tipo));
    }
    if (activeTab === "relevantes") {
      return alertas.filter((alerta) => Boolean(alerta.relevante));
    }
    return alertas;
  }, [activeTab, alertas]);

  const ativos = subscricoes.filter((item) => Boolean(item.ativo));
  const seteDias = referenciaTemporal - 7 * 24 * 60 * 60 * 1000;
  const encontradosSemana = alertas.filter((alerta) => {
    const data = new Date(alerta.data_deteccao);
    if (Number.isNaN(data.getTime())) return false;
    return data.getTime() >= seteDias;
  }).length;

  async function gerarNovaAnalise(alerta: Alerta) {
    const token = session?.access_token;
    if (!token) return;

    setCreatingFor(alerta.id);
    setActionError(null);

    try {
      const resposta = await fetch(`${API_URL}/analises/criar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ concurso_id: alerta.concurso_id }),
      });

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => null);
        throw new Error(
          dados?.detail || "Não foi possível criar a nova análise AI.",
        );
      }

      window.location.href = "/analises";
    } catch (erro) {
      setActionError(
        erro instanceof Error
          ? erro.message
          : "Não foi possível criar a nova análise AI.",
      );
    } finally {
      setCreatingFor(null);
    }
  }

  return (
    <main className="site-container">
      <div className="alerts-page">
        <header className="alerts-header">
          <div>
            <div className="alerts-icon">
              <Bell size={38} />
            </div>

            <h1>Alertas</h1>

            <p>
              Acompanha novidades, prazos e alterações dos concursos que segues.
            </p>
          </div>

          <button className="new-alert" disabled>
            {ativos.length} concursos acompanhados
          </button>
        </header>

        <div className="alerts-layout">
          <section className="alerts-main">
            <nav className="alerts-tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  className={activeTab === tab.id ? "active" : ""}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="alerts-list">
              {loading ? (
                <p className="alerts-empty">
                  <Loader2 size={20} className="spin" /> A carregar alertas...
                </p>
              ) : error ? (
                <p className="alerts-empty" role="alert">{error}</p>
              ) : filtrados.length === 0 ? (
                <p className="alerts-empty">
                  Ainda não há alertas configurados para concursos.
                </p>
              ) : (
                filtrados.map((alerta) => (
                  <AlertCard
                    key={alerta.id}
                    alerta={alerta}
                    onGerarAnalise={
                      creatingFor === null ? gerarNovaAnalise : undefined
                    }
                  />
                ))
              )}
            </div>

            {actionError && (
              <p className="alerts-action-error" role="alert">
                {actionError}
              </p>
            )}

            <section className="found-projects">
              <h2>Concursos acompanhados</h2>

              {ativos.length === 0 ? (
                <p className="alerts-empty">
                  Ativa alertas nos Favoritos para acompanhar concursos.
                </p>
              ) : (
                <div className="monitored-list">
                  {ativos.slice(0, 6).map((item) => (
                    <article key={item.concurso_id}>
                      <span>
                        {item.e_favorito ? "Favorito" : item.tem_analise ? "Análise AI" : "Alerta"}
                      </span>
                      <strong>{item.titulo}</strong>
                      {item.entidade && <small>{item.entidade}</small>}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </section>

          <aside className="alerts-side">
            <div className="summary-card">
              <h3>Resumo dos teus alertas</h3>

              <strong>{ativos.length}</strong>
              <span>Concursos acompanhados</span>

              <strong>{alertas.length}</strong>
              <span>Alertas registados</span>

              <strong>{encontradosSemana}</strong>
              <span>Detetados esta semana</span>
            </div>

            <div className="help-card">
              <h3>Como funcionam os alertas?</h3>

              <p>
                Os alertas usam os concursos que acompanhas: favoritos, alertas ativos
                e análises AI. A leitura documental futura alimentará estes mesmos
                eventos, sem duplicar o pipeline.
              </p>

              <Sparkles size={18} />
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
