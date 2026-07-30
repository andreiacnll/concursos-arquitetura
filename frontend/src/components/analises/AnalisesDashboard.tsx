"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Clock3,
  CheckCircle2,
  FileSearch,
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

                {analise.estado === "concluida" ? (
                  <Link href={`/analise/${analise.concurso_id}`} className="analise-view-btn">
                    Ver análise
                  </Link>
                ) : (
                  <span className="analise-view-btn is-disabled">
                    Acompanhar aqui
                  </span>
                )}
              </div>
            );
          })}
        </section>
      )}

    </div>
  );
}
