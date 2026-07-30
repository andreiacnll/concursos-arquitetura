"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  Clock3,
  CheckCircle2,
  FileSearch,
  Building2,
  CircleDot
} from "lucide-react";
import "./analises.css";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

type Analise = {
  id: string;
  titulo: string;
  entidade: string;
  estado: string;
  score?: number;
  progresso?: number;
};

export default function AnalisesDashboard() {

  const [analises, setAnalises] = useState<Analise[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Buscar análises reais do backend
    fetch(`${API_URL}/analises`)
      .then(res => res.json())
      .then((dados: Analise[]) => {
        setAnalises(dados);
        setLoading(false);
      })
      .catch(() => {
        // Fallback: análises conhecidas
        setAnalises([
          {
            id: "450837",
            titulo: "Requalificação do Mercado Municipal de Castelo Branco",
            entidade: "Município de Castelo Branco",
            estado: "concluida",
            score: 86,
          },
          {
            id: "420959",
            titulo: "Reabilitação da Escola Secundária do Lumiar",
            entidade: "Município de Lisboa",
            estado: "concluida",
            score: 85,
          },
        ]);
        setLoading(false);
      });
  }, []);

  const totalAnalises = analises.length;
  const concluidas = analises.filter(a => a.estado === "concluida").length;
  const emProcessamento = analises.filter(a => a.estado === "processamento" || a.estado === "a_gerar").length;

  return (
    <div className="analises-page">

      <header className="analises-header">
        <div>
          <h1>Análises <span>IA</span></h1>
          <p>Acompanha as análises dos concursos que selecionaste.</p>
        </div>
        <Link href="/entidades">
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
          <Clock3 size={26} /><strong>0</strong>
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
      ) : analises.length === 0 ? (
        <section className="analises-card">
          <p style={{ padding: "24px", textAlign: "center", color: "#777" }}>
            Nenhuma análise disponível. Explora concursos para criar a primeira análise.
          </p>
        </section>
      ) : (
        <section className="analises-card">
          <h2>Análises disponíveis</h2>
          {analises.map((analise) => (
            <div key={analise.id} className="analise-item">
              <div>
                <div className="analise-title">
                  <CheckCircle2 size={20} />
                  <h3>{analise.titulo}</h3>
                </div>
                <p>{analise.entidade}</p>
              </div>

              {analise.score && (
                <div className="score-box">
                  <strong>Score IA</strong>
                  <br />
                  {analise.score} / 100
                </div>
              )}

              <Link href={`/analise/${analise.id}`}>
                {analise.estado === "concluida" ? "Ver análise" : "Acompanhar"}
              </Link>
            </div>
          ))}
        </section>
      )}

    </div>
  );
}