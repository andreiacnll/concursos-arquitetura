"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Clock3,
  CheckCircle2,
  FileSearch,
  Trash2,
  XCircle,
} from "lucide-react";
import "./analises.css";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";

type Analise = {
  id: number;
  tipo?: "analise" | "job";
  concurso_id: number;
  titulo: string;
  entidade: string;
  estado: string;
  progresso: number;
  erro?: string | null;
  created_at: string;
  updated_at: string;
  score?: number | null;
  pode_apagar?: boolean | number;
  pode_cancelar?: boolean | number;
};

type Confirmacao = {
  tipo: "cancelar" | "apagar";
  analise: Analise;
};

function statusLabel(estado: string): { texto: string; icone: string; classe: string } {
  switch (estado) {
    case "aguarda":
      return { texto: "⏳ Na fila", icone: "⏳", classe: "status-gerando" };
    case "extracao":
      return { texto: "📥 A recolher documentos", icone: "📥", classe: "status-processando" };
    case "processamento":
      return { texto: "⚙️ A analisar", icone: "⚙️", classe: "status-processando" };
    case "geracao":
      return { texto: "📝 A gerar análise", icone: "📝", classe: "status-processando" };
    case "concluida":
      return { texto: "✓ Concluída", icone: "✓", classe: "status-concluida" };
    case "cancelada":
      return { texto: "Cancelada", icone: "×", classe: "status-cancelada" };
    case "erro":
      return { texto: "⚠️ Erro", icone: "⚠️", classe: "status-erro" };
    default:
      return { texto: estado, icone: "•", classe: "" };
  }
}

export default function AnalisesDashboard() {

  const { session } = useAuth();
  const [analises, setAnalises] = useState<Analise[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    fetch(`${API_URL}/analises`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("Não foi possível carregar as análises.");
        }
        return res.json();
      })
      .then((dados: unknown) => {
        let lista: Analise[] = [];
        if (Array.isArray(dados)) {
          lista = dados;
        } else if (dados && typeof dados === 'object') {
          const obj = dados as Record<string, unknown>;
          lista = (obj.analises || obj.items || obj.resultados || []) as Analise[];
        }
        setAnalises(lista);
        setError(null);
        setLoading(false);
      })
      .catch((erro) => {
        setError(
          erro instanceof Error
            ? erro.message
            : "Não foi possível carregar as análises.",
        );
        setLoading(false);
      });
  }, [session?.access_token]);

  async function confirmarAcao() {
    const token = session?.access_token;
    if (!token || !confirmacao) return;

    const { tipo, analise } = confirmacao;
    setActionLoading(true);
    setActionError(null);

    try {
      const resposta = await fetch(
        tipo === "cancelar"
          ? `${API_URL}/analises/${analise.id}/cancelar`
          : `${API_URL}/analises/${analise.id}`,
        {
          method: tipo === "cancelar" ? "POST" : "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        },
      );

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => null);
        throw new Error(
          dados?.detail || "Não foi possível atualizar a análise.",
        );
      }

      if (tipo === "cancelar") {
        const dados = await resposta.json();
        setAnalises((atuais) =>
          atuais.map((item) =>
            item.tipo === "job" && item.id === analise.id
              ? {
                  ...item,
                  estado: dados.estado || "cancelada",
                  pode_cancelar: false,
                  updated_at: dados.updated_at || item.updated_at,
                }
              : item,
          ),
        );
      } else {
        setAnalises((atuais) =>
          atuais.filter(
            (item) =>
              !(item.tipo === "analise" && item.id === analise.id),
          ),
        );
      }

      setConfirmacao(null);
    } catch (erro) {
      setActionError(
        erro instanceof Error
          ? erro.message
          : "Não foi possível atualizar a análise.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  const totalAnalises = analises.length;
  const concluidas = analises.filter(a => a.estado === "concluida").length;
  const emFila = analises.filter(a => a.estado === "aguarda").length;
  const emProcessamento = analises.filter(a =>
    ["extracao", "processamento", "geracao"].includes(a.estado),
  ).length;

  return (
    <div className="analises-page">

      <header className="analises-header">
        <div>
          <h1>Análises <span>IA</span></h1>
          <p>Acompanha as análises dos concursos que selecionaste.</p>
        </div>
        <Link href="/">
          <button>Explorar concursos</button>
        </Link>
      </header>

      <section className="analises-stats">
        <div>
          <Activity size={26} /><strong>{totalAnalises}</strong>
          <p>Total de análises</p>
          <span>Disponíveis</span>
        </div>
        <div>
          <FileSearch size={26} /><strong>{emProcessamento}</strong>
          <p>A processar</p>
          <span>Em análise</span>
        </div>
        <div>
          <Clock3 size={26} /><strong>{emFila}</strong>
          <p>Em fila</p>
          <span>A aguardar</span>
        </div>
        <div>
          <CheckCircle2 size={26} /><strong>{concluidas}</strong>
          <p>Concluídas</p>
          <span>Disponíveis</span>
        </div>
      </section>

      {loading ? (
        <section className="analises-card">
          <p style={{ padding: "24px", textAlign: "center", color: "#777" }}>A carregar análises...</p>
        </section>
      ) : error ? (
        <section className="analises-card">
          <p role="alert" style={{ padding: "24px", textAlign: "center", color: "#a33" }}>
            {error}
          </p>
        </section>
      ) : !Array.isArray(analises) || analises.length === 0 ? (
        <section className="analises-card">
          <p style={{ padding: "24px", textAlign: "center", color: "#777" }}>
            Nenhuma análise disponível. Explora concursos para criar a primeira análise.
          </p>
        </section>
      ) : (
        <section className="analises-card">
          <h2>Histórico de análises geradas</h2>
          {actionError && (
            <p className="analise-action-error" role="alert">
              {actionError}
            </p>
          )}
          {analises.map((analise) => {
            const st = statusLabel(analise.estado);
            return (
              <div key={`${analise.tipo ?? "job"}-${analise.id}`} className="analise-item">
                <div>
                  <div className="analise-title">
                    <span className={`analise-status-badge ${st.classe}`}>
                      {st.icone}
                    </span>
                    <h3>{analise.titulo}</h3>
                  </div>
                  <p>{analise.entidade}</p>
                  <p className="analise-date">
                    {analise.estado === "concluida" ? "Análise de " : "Pedido em "}
                    {new Date(analise.created_at).toLocaleString("pt-PT")}
                  </p>
                </div>

                <div className="analise-status-info">
                  <span className={`analise-status-label ${st.classe}`}>
                    {st.texto}
                  </span>
                </div>

                <div className="score-box">
                  <strong>
                    {analise.estado === "concluida" && analise.score != null
                      ? "Score CNLL"
                      : "Progresso"}
                  </strong>
                  <br />
                  {analise.estado === "concluida" && analise.score != null
                    ? `${analise.score}/100`
                    : `${analise.progresso}%`}
                </div>

                <div className="analise-actions">
                  {analise.estado === "concluida" ? (
                    <>
                      <Link href={`/analise/${analise.concurso_id}`} className="analise-view-btn">
                        Ver análise
                      </Link>
                      {Boolean(analise.pode_apagar) && (
                        <button
                          type="button"
                          className="analise-lifecycle-btn is-delete"
                          onClick={() =>
                            setConfirmacao({ tipo: "apagar", analise })
                          }
                        >
                          <Trash2 size={15} />
                          Apagar análise
                        </button>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="analise-view-btn is-disabled">
                        {analise.estado === "cancelada"
                          ? "Processamento cancelado"
                          : "Acompanhar aqui"}
                      </span>
                      {Boolean(analise.pode_cancelar) && (
                        <button
                          type="button"
                          className="analise-lifecycle-btn is-cancel"
                          onClick={() =>
                            setConfirmacao({ tipo: "cancelar", analise })
                          }
                        >
                          <XCircle size={15} />
                          Cancelar análise
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {confirmacao && (
        <div
          className="analise-confirm-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !actionLoading) {
              setConfirmacao(null);
            }
          }}
        >
          <section
            className="analise-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="analise-confirm-title"
          >
            <h2 id="analise-confirm-title">
              {confirmacao.tipo === "cancelar"
                ? "Cancelar análise"
                : "Apagar análise"}
            </h2>
            <p>
              {confirmacao.tipo === "cancelar"
                ? "Tem a certeza que pretende cancelar esta análise?"
                : "Esta ação irá remover a análise gerada. O concurso continuará disponível."}
            </p>
            <strong>{confirmacao.analise.titulo}</strong>
            <div className="analise-confirm-actions">
              <button
                type="button"
                onClick={() => setConfirmacao(null)}
                disabled={actionLoading}
              >
                Voltar
              </button>
              <button
                type="button"
                className="is-danger"
                onClick={confirmarAcao}
                disabled={actionLoading}
              >
                {actionLoading
                  ? "A processar..."
                  : confirmacao.tipo === "cancelar"
                    ? "Cancelar análise"
                    : "Apagar análise"}
              </button>
            </div>
          </section>
        </div>
      )}

    </div>
  );
}
