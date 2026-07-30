"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Clock3,
  CheckCircle2,
  FileSearch,
  RefreshCw,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";
import "./analises.css";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";

type Analise = {
  id: number;
  tipo?: "analise" | "job";
  user_id?: string | null;
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
  pode_repetir?: boolean | number;
  pode_atualizar?: boolean | number;
};

type Confirmacao = {
  tipo: "cancelar" | "apagar";
  analise: Analise;
};

function ativo(valor: boolean | number | undefined) {
  return valor === true || valor === 1;
}

function statusLabel(estado: string): { texto: string; icone: string; classe: string } {
  switch (estado) {
    case "aguarda":
      return { texto: "⏳ Na fila", icone: "⏳", classe: "status-gerando" };
    case "extracao":
      return { texto: "📄 A recolher documentos", icone: "📄", classe: "status-processando" };
    case "processamento":
      return { texto: "⚙️ A analisar documentos", icone: "⚙️", classe: "status-processando" };
    case "geracao":
      return { texto: "✨ A criar análise", icone: "✨", classe: "status-processando" };
    case "concluida":
      return { texto: "✓ Disponível", icone: "✓", classe: "status-concluida" };
    case "erro":
      return { texto: "❌ Erro na análise", icone: "❌", classe: "status-erro" };
    case "cancelada":
      return { texto: "⛔ Cancelada", icone: "⛔", classe: "status-cancelada" };
    default:
      return { texto: estado, icone: "•", classe: "" };
  }
}

function normalizarAnalise(valor: unknown): Analise {
  const item = (valor ?? {}) as Partial<Analise>;
  return {
    id: Number(item.id),
    tipo: item.tipo ?? "job",
    user_id: item.user_id,
    concurso_id: Number(item.concurso_id),
    titulo: item.titulo ?? "Concurso sem título",
    entidade: item.entidade ?? "Entidade não indicada",
    estado: item.estado ?? "aguarda",
    progresso: Number(item.progresso ?? 0),
    erro: item.erro ?? null,
    created_at: item.created_at ?? new Date().toISOString(),
    updated_at: item.updated_at ?? new Date().toISOString(),
    score: item.score ?? null,
    pode_apagar: item.pode_apagar,
    pode_cancelar: item.pode_cancelar,
    pode_repetir: item.pode_repetir,
    pode_atualizar: item.pode_atualizar,
  };
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
        const obj = dados as { analises?: unknown[]; items?: unknown[]; resultados?: unknown[] };
        const lista = Array.isArray(dados)
          ? dados
          : obj.analises || obj.items || obj.resultados || [];
        setAnalises(lista.map(normalizarAnalise));
        setError(null);
      })
      .catch((erro: unknown) => {
        setError(
          erro instanceof Error
            ? erro.message
            : "Não foi possível carregar as análises.",
        );
      })
      .finally(() => setLoading(false));
  }, [session?.access_token]);

  function inserirOuAtualizar(item: Analise) {
    setAnalises((atuais) => {
      const semDuplicado = atuais.filter(
        (atual) => !(atual.tipo === item.tipo && atual.id === item.id),
      );
      return [item, ...semDuplicado];
    });
  }

  async function executarAcaoRapida(
    tipo: "repetir" | "atualizar",
    analise: Analise,
  ) {
    const token = session?.access_token;
    if (!token) return;

    setActionLoading(true);
    setActionError(null);

    try {
      const url =
        tipo === "repetir"
          ? `${API_URL}/analises/${analise.id}/repetir`
          : `${API_URL}/analises/concurso/${analise.concurso_id}/atualizar`;
      const resposta = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => null);
        throw new Error(
          dados?.detail || "Não foi possível atualizar a análise.",
        );
      }

      inserirOuAtualizar(normalizarAnalise(await resposta.json()));
    } catch (erro: unknown) {
      setActionError(
        erro instanceof Error
          ? erro.message
          : "Não foi possível atualizar a análise.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function confirmarAcao() {
    const token = session?.access_token;
    if (!token || !confirmacao) return;

    const { tipo, analise } = confirmacao;
    setActionLoading(true);
    setActionError(null);

    try {
      const apagarJob = tipo === "apagar" && analise.tipo === "job";
      const resposta = await fetch(
        tipo === "cancelar"
          ? `${API_URL}/analises/${analise.id}/cancelar`
          : apagarJob
          ? `${API_URL}/analises/jobs/${analise.id}`
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
                  progresso: dados.progresso ?? item.progresso,
                  pode_cancelar: false,
                  pode_apagar: true,
                  updated_at: dados.updated_at || item.updated_at,
                }
              : item,
          ),
        );
      } else {
        setAnalises((atuais) =>
          atuais.filter(
            (item) => !(item.tipo === analise.tipo && item.id === analise.id),
          ),
        );
      }

      setConfirmacao(null);
    } catch (erro: unknown) {
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
      ) : analises.length === 0 ? (
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
            const concluida = analise.estado === "concluida";
            const emErro = analise.estado === "erro";
            const cancelada = analise.estado === "cancelada";

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
                    {concluida ? "Análise de " : "Pedido em "}
                    {new Date(analise.created_at).toLocaleString("pt-PT")}
                  </p>
                  {emErro && analise.erro && (
                    <p className="analise-error-detail">{analise.erro}</p>
                  )}
                </div>

                <div className="analise-status-info">
                  <span className={`analise-status-label ${st.classe}`}>
                    {st.texto}
                  </span>
                </div>

                <div className="score-box">
                  <strong>
                    {concluida && analise.score != null
                      ? "Score CNLL"
                      : "Progresso"}
                  </strong>
                  <br />
                  {concluida && analise.score != null
                    ? `${analise.score}/100`
                    : `${analise.progresso}%`}
                </div>

                <div className="analise-actions">
                  {concluida && (
                    <Link href={`/analise/${analise.concurso_id}`} className="analise-view-btn">
                      Ver análise
                    </Link>
                  )}

                  {ativo(analise.pode_atualizar) && (
                    <button
                      type="button"
                      className="analise-lifecycle-btn is-update"
                      onClick={() => executarAcaoRapida("atualizar", analise)}
                      disabled={actionLoading}
                    >
                      <RefreshCw size={15} />
                      Atualizar análise
                    </button>
                  )}

                  {ativo(analise.pode_repetir) && (
                    <button
                      type="button"
                      className="analise-lifecycle-btn is-retry"
                      onClick={() => executarAcaoRapida("repetir", analise)}
                      disabled={actionLoading}
                    >
                      <RotateCcw size={15} />
                      Repetir análise
                    </button>
                  )}

                  {!concluida && !emErro && !cancelada && (
                    <span className="analise-view-btn is-disabled">
                      Acompanhar aqui
                    </span>
                  )}

                  {ativo(analise.pode_cancelar) && (
                    <button
                      type="button"
                      className="analise-lifecycle-btn is-cancel"
                      onClick={() =>
                        setConfirmacao({ tipo: "cancelar", analise })
                      }
                      disabled={actionLoading}
                    >
                      <XCircle size={15} />
                      Cancelar análise
                    </button>
                  )}

                  {ativo(analise.pode_apagar) && (
                    <button
                      type="button"
                      className="analise-lifecycle-btn is-delete"
                      onClick={() =>
                        setConfirmacao({ tipo: "apagar", analise })
                      }
                      disabled={actionLoading}
                    >
                      <Trash2 size={15} />
                      Apagar
                    </button>
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
                : confirmacao.analise.tipo === "job"
                ? "Esta ação remove o pedido de análise em erro ou cancelado. O concurso continuará disponível."
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
                    : "Apagar"}
              </button>
            </div>
          </section>
        </div>
      )}

    </div>
  );
}
