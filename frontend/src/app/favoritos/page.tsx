"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PrivateLayout from "@/components/layout/PrivateLayout";
import { Bell, Filter, Heart, Star, Sparkles, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import AnalysisConfirmationModal from "@/components/analises/AnalysisConfirmationModal";
import RecommendationList from "@/components/recommendations/RecommendationList";
import type { RecommendationCard as RecommendationCardType } from "@/components/recommendations/recommendation-types";
import { API_URL } from "@/lib/api";
import {
  ANALYSIS_POLL_INTERVAL_MS,
  fetchAnalysisJobState,
  isActiveAnalysisStatus,
  normalizeAnalysisJob,
  type AnalysisJobState,
} from "@/lib/analysis-jobs";
import CompetitionFiltersSidebar from "@/components/CompetitionFiltersSidebar";
import {
  DEFAULT_COMPETITION_FILTERS,
  hasActiveCompetitionFilters,
  matchesCompetitionFilters,
  type CompetitionFiltersState,
} from "@/components/competition-filters";

type Favorito = {
  id: number;
  concurso_id: number;
  titulo: string;
  entidade: string;
  preco_base?: string;
  data_limite?: string;
  localizacao?: string;
  distrito?: string | null;
  municipio?: string | null;
  tipo_procedimento?: string | null;
  data_fim_calculada?: string | null;
  data_entrega_propostas?: string | null;
  data_publicacao_iso?: string | null;
  valor_procedimento?: string | number | null;
  valor_obra?: string | number | null;
  score?: number | null;
  tem_analise?: boolean;
  analise_estado?: string;
  analise_stage?: string | null;
  analise_job_id?: number | null;
  analise_id?: number | null;
  alerta_ativo?: boolean;
};

type AnaliseJob = {
  concurso_id: number;
  estado: string;
};

type AlertaSubscricao = {
  concurso_id: number;
  ativo: boolean | number;
};

type RecommendationScore = Pick<RecommendationCardType, "competition_id" | "compatibility_score">;

export default function FavoritosPage() {

  const { user, session, loading: authLoading } = useAuth();
  const router = useRouter();
  const [favoritos, setFavoritos] = useState<Favorito[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtro, setFiltro] = useState<string>("todos");
  const [filters, setFilters] = useState<CompetitionFiltersState>(
    DEFAULT_COMPETITION_FILTERS,
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [confirmacao, setConfirmacao] = useState<Favorito | null>(null);
  const [recommendationScores, setRecommendationScores] = useState<
    Map<number, number>
  >(new Map());
  const [recommendationCards, setRecommendationCards] = useState<RecommendationCardType[]>([]);
  const [recommendationAnalysisJobs, setRecommendationAnalysisJobs] = useState<
    Record<number, AnalysisJobState>
  >({});

  // Redirecionar se não autenticado
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) {
      setRecommendationScores(new Map());
      setRecommendationCards([]);
      setRecommendationAnalysisJobs({});
      return;
    }

    const recommendationCardsPromise = fetch(`${API_URL}/company/recommendation-cards`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).catch(() => null);

    Promise.all([
      fetch(`${API_URL}/favoritos`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_URL}/analises`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      fetch(`${API_URL}/alertas/subscricoes`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
      recommendationCardsPromise,
    ])
      .then(async ([favoritosResponse, analisesResponse, alertasResponse, recommendationsResponse]) => {
        if (!favoritosResponse.ok || !analisesResponse.ok || !alertasResponse.ok) {
          throw new Error("Não foi possível carregar os favoritos.");
        }

        return Promise.all([
          favoritosResponse.json(),
          analisesResponse.json(),
          alertasResponse.json(),
          recommendationsResponse && recommendationsResponse.ok
            ? recommendationsResponse.json()
            : Promise.resolve([]),
        ]);
      })
      .then(([favoritosData, analisesData, alertasData, recommendationCardsData]) => {
        const jobs = (analisesData.analises ?? []) as AnaliseJob[];
        const jobsMap = new Map<number, AnalysisJobState>();
        const analysisJobsByCompetition: Record<number, AnalysisJobState> = {};
        for (const item of jobs) {
          const job = normalizeAnalysisJob(item);
          if (!job) continue;
          jobsMap.set(job.concurso_id, job);
          analysisJobsByCompetition[job.concurso_id] = job;
        }
        const cards = Array.isArray(recommendationCardsData)
          ? (recommendationCardsData as RecommendationCardType[])
          : [];
        const scoresMap = new Map<number, number>();
        for (const card of cards as RecommendationScore[]) {
          if (typeof card?.competition_id === "number" && typeof card?.compatibility_score === "number") {
            scoresMap.set(card.competition_id, card.compatibility_score);
          }
        }
        const subscricoes = (
          alertasData.subscricoes ?? []
        ) as AlertaSubscricao[];
        const alertasMap = new Map(
          subscricoes.map((item) => [
            item.concurso_id,
            Boolean(item.ativo),
          ]),
        );
        const lista = (favoritosData.favoritos ?? []) as Favorito[];

        setFavoritos(
          lista.map((favorito) => ({
            ...favorito,
            score:
              typeof favorito.score === "number"
                ? favorito.score
                : scoresMap.get(favorito.concurso_id) ?? null,
            tem_analise: jobsMap.has(favorito.concurso_id),
            analise_estado: jobsMap.get(favorito.concurso_id)?.status,
            analise_stage: jobsMap.get(favorito.concurso_id)?.stage,
            analise_job_id: jobsMap.get(favorito.concurso_id)?.job_id,
            analise_id: jobsMap.get(favorito.concurso_id)?.analysis_id,
            alerta_ativo: alertasMap.get(favorito.concurso_id) ?? true,
          })),
        );
        setRecommendationScores(scoresMap);
        setRecommendationCards(cards);
        setRecommendationAnalysisJobs(analysisJobsByCompetition);
        setLoading(false);
      })
      .catch(() => {
        setFavoritos([]);
        setLoading(false);
        setRecommendationScores(new Map());
        setRecommendationCards([]);
        setRecommendationAnalysisJobs({});
      });
  }, [session?.access_token]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;
    const active = favoritos.filter(
      (fav) =>
        fav.analise_job_id &&
        isActiveAnalysisStatus(fav.analise_estado),
    );
    if (active.length === 0) return;

    const timer = window.setInterval(() => {
      active.forEach((fav) => {
        if (!fav.analise_job_id) return;
        fetchAnalysisJobState(token, fav.analise_job_id)
          .then((job) => {
            setRecommendationAnalysisJobs((current) => ({
              ...current,
              [job.concurso_id]: job,
            }));
            setFavoritos((current) =>
              current.map((item) =>
                item.concurso_id === job.concurso_id
                  ? {
                      ...item,
                      tem_analise: true,
                      analise_estado: job.status,
                      analise_stage: job.stage,
                      analise_job_id: job.job_id,
                      analise_id: job.analysis_id,
                    }
                  : item,
              ),
            );
          })
          .catch(() => {});
      });
    }, ANALYSIS_POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [favoritos, session?.access_token]);

  async function removerFavorito(favorito: Favorito) {
    const token = session?.access_token;
    if (!token) return;

    const response = await fetch(
      `${API_URL}/favoritos/${favorito.concurso_id}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (response.ok) {
      setFavoritos((current) =>
        current.filter((item) => item.id !== favorito.id),
      );
    }
  }

  async function alternarAlertas(favorito: Favorito) {
    const token = session?.access_token;
    if (!token) return;

    const ativo = Boolean(favorito.alerta_ativo);
    const response = await fetch(
      `${API_URL}/alertas/${favorito.concurso_id}/${ativo ? "desativar" : "ativar"}`,
      {
        method: ativo ? "DELETE" : "POST",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (response.ok) {
      setFavoritos((current) =>
        current.map((item) =>
          item.id === favorito.id
            ? { ...item, alerta_ativo: !ativo }
            : item,
        ),
      );
    }
  }

  async function criarAnalise(favorito: Favorito) {
    const token = session?.access_token;
    if (!token) {
      throw new Error("A sessão terminou. Volta a iniciar sessão.");
    }

    const response = await fetch(`${API_URL}/analises/criar`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ concurso_id: favorito.concurso_id }),
    });

    if (!response.ok) {
      const dados = await response.json().catch(() => null);
      throw new Error(
        dados?.detail || "Não foi possível colocar a análise na fila.",
      );
    }

    const job = normalizeAnalysisJob(await response.json());
    if (job) {
      setRecommendationAnalysisJobs((current) => ({
        ...current,
        [job.concurso_id]: job,
      }));
    }

    setFavoritos((current) =>
      current.map((item) =>
        item.concurso_id === favorito.concurso_id
          ? {
              ...item,
              tem_analise: true,
              analise_estado: job?.status || "queued",
              analise_stage: job?.stage || "queued",
              analise_job_id: job?.job_id || null,
              analise_id: job?.analysis_id || null,
            }
          : item,
      ),
    );
  }

  if (authLoading || !user) {
    return (
      <PrivateLayout>
        <main className="site-container" style={{ paddingTop: "32px", textAlign: "center", padding: "60px" }}>
          <Loader2 size={32} className="spin" style={{ animation: "spin 1s linear infinite" }} />
          <p style={{ color: "#777", marginTop: "16px" }}>A verificar sessão...</p>
        </main>
      </PrivateLayout>
    );
  }

  const hasActiveFilters = hasActiveCompetitionFilters(filters);
  const districts = Array.from(
    new Set(
      favoritos
        .map((item) => item.distrito ?? item.localizacao)
        .filter((item): item is string => Boolean(item)),
    ),
  ).sort((a, b) => a.localeCompare(b, "pt"));

  const favoritosFiltradosPorEstado =
    filtro === "todos"
      ? favoritos
      : filtro === "analisado"
        ? favoritos.filter((fav) => fav.tem_analise)
        : favoritos;

  const filtrados = favoritosFiltradosPorEstado.filter((fav) =>
    matchesCompetitionFilters(
      {
        titulo: fav.titulo,
        entidade: fav.entidade,
        distrito: fav.distrito ?? fav.localizacao ?? null,
        municipio: fav.municipio ?? fav.localizacao ?? null,
        preco_base: fav.preco_base ?? null,
        valor_procedimento: fav.valor_procedimento ?? null,
        valor_obra: fav.valor_obra ?? null,
        data_limite: fav.data_limite ?? null,
        data_entrega_propostas:
          fav.data_entrega_propostas ?? fav.data_limite ?? null,
        data_fim_calculada: fav.data_fim_calculada ?? fav.data_limite ?? null,
        data_publicacao_iso: fav.data_publicacao_iso ?? null,
        data: fav.data_publicacao_iso ?? null,
        tipo_procedimento: fav.tipo_procedimento ?? null,
      },
      filters,
    ),
  );

  return (
    <PrivateLayout>
      <main className="site-container" style={{ paddingTop: "32px" }}>

        <header style={{ marginBottom: "28px" }}>
          <h1 style={{ fontSize: "32px", fontWeight: 500, marginBottom: "8px" }}>
            <Heart size={28} style={{ marginRight: "10px", color: "#607b43" }} />
            Favoritos
          </h1>
          <p style={{ color: "#777", fontSize: "14px" }}>
            {favoritos.length} concurso{favoritos.length !== 1 ? "s" : ""} guardado{favoritos.length !== 1 ? "s" : ""}
          </p>
        </header>

        <button
          type="button"
          className="filters-mobile-button"
          onClick={() => setFiltersOpen(true)}
        >
          <Filter size={16} />
          Filtros
        </button>

        <div className="listing-shell favoritos-listing-shell">
          <CompetitionFiltersSidebar
            items={favoritos.map((fav) => ({
              titulo: fav.titulo,
              entidade: fav.entidade,
              distrito: fav.distrito ?? fav.localizacao ?? null,
              municipio: fav.municipio ?? fav.localizacao ?? null,
              preco_base: fav.preco_base ?? null,
              valor_procedimento: fav.valor_procedimento ?? null,
              valor_obra: fav.valor_obra ?? null,
              data_limite: fav.data_limite ?? null,
              data_entrega_propostas:
                fav.data_entrega_propostas ?? fav.data_limite ?? null,
              data_fim_calculada: fav.data_fim_calculada ?? fav.data_limite ?? null,
              data_publicacao_iso: fav.data_publicacao_iso ?? null,
              data: fav.data_publicacao_iso ?? null,
              tipo_procedimento: fav.tipo_procedimento ?? null,
            }))}
            districts={districts}
            filters={filters}
            onChange={setFilters}
            onClear={() => setFilters(DEFAULT_COMPETITION_FILTERS)}
            hasActiveFilters={hasActiveFilters}
          />

          <CompetitionFiltersSidebar
            items={favoritos}
            districts={districts}
            filters={filters}
            onChange={setFilters}
            onClear={() => setFilters(DEFAULT_COMPETITION_FILTERS)}
            hasActiveFilters={hasActiveFilters}
            mobileOpen={filtersOpen}
            onCloseMobile={() => setFiltersOpen(false)}
          />

          <div className="results-panel">
        <h2 style={{ fontSize: "22px", fontWeight: 550, marginBottom: "16px" }}>
          Os meus Favoritos
        </h2>

        <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
          {["todos", "favorito", "analisado"].map((tipo) => (
            <button
              key={tipo}
              onClick={() => setFiltro(tipo)}
              style={{
                padding: "8px 18px",
                borderRadius: "10px",
                border: filtro === tipo ? "2px solid #607b43" : "1px solid #ddd",
                background: filtro === tipo ? "#f0f4ea" : "white",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: filtro === tipo ? 600 : 400,
                color: filtro === tipo ? "#607b43" : "#555",
              }}
            >
              {tipo === "todos" ? "Todos" : tipo === "favorito" ? "Favoritos" : "Com análise"}
            </button>
          ))}
        </div>

        {loading ? (
          <p style={{ color: "#777", padding: "40px 0", textAlign: "center" }}>A carregar favoritos...</p>
        ) : filtrados.length === 0 ? (
          <div style={{
            textAlign: "center",
            padding: "60px 20px",
            background: "white",
            borderRadius: "18px",
            border: "1px solid #e8e8e2",
          }}>
            <Heart size={48} style={{ color: "#ddd", marginBottom: "16px" }} />
            <h3 style={{ fontWeight: 500, marginBottom: "8px" }}>Nenhum favorito</h3>
            <p style={{ color: "#777", fontSize: "14px" }}>
              Guarda concursos como favoritos para os acompanhares aqui.
            </p>
            <Link href="/entidades">
              <button style={{
                marginTop: "16px",
                padding: "10px 24px",
                background: "#111",
                color: "white",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
              }}>
                Explorar concursos
              </button>
            </Link>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {filtrados.map((fav) => (
              <div key={fav.id} style={{
                display: "flex",
                alignItems: "center",
                gap: "16px",
                padding: "20px 24px",
                background: "white",
                borderRadius: "16px",
                border: "1px solid #e8e8e2",
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <Star size={16} style={{ color: fav.tem_analise ? "#607b43" : "#ccc" }} />
                    <h3 style={{ fontSize: "16px", fontWeight: 600, margin: 0 }}>{fav.titulo}</h3>
                  </div>
                  <p style={{ fontSize: "13px", color: "#777", margin: 0 }}>{fav.entidade}</p>
                  <div style={{ display: "flex", gap: "16px", marginTop: "8px", fontSize: "12px", color: "#999" }}>
                    {fav.preco_base && <span>💰 {fav.preco_base}</span>}
                    {fav.data_limite && <span>📅 {fav.data_limite}</span>}
                  </div>
                </div>

                {(typeof fav.score === "number" || recommendationScores.has(fav.concurso_id)) && (
                  <div style={{
                    textAlign: "center",
                    padding: "8px 16px",
                    background: "#f0f4ea",
                    borderRadius: "10px",
                  }}>
                    <div style={{ fontSize: "11px", color: "#777" }}>Score</div>
                    <strong style={{ fontSize: "20px", color: "#607b43" }}>
                      {typeof fav.score === "number"
                        ? fav.score
                        : recommendationScores.get(fav.concurso_id) ?? "—"}
                    </strong>
                  </div>
                )}

                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  {/* Botão "Criar análise AI" ou "Ver análise" */}
                  {fav.tem_analise && ["concluida", "completed", "partial"].includes(fav.analise_estado || "") ? (
                    <Link href={`/analise/${fav.concurso_id}`} style={{
                      padding: "10px 20px",
                      background: "#111",
                      color: "white",
                      border: "none",
                      borderRadius: "10px",
                      textDecoration: "none",
                      fontSize: "13px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}>
                      Ver análise AI
                    </Link>
                  ) : fav.tem_analise ? (
                    <Link href="/analises" style={{
                      padding: "10px 20px",
                      background: "#111",
                      color: "white",
                      borderRadius: "10px",
                      textDecoration: "none",
                      fontSize: "13px",
                    }}>
                      {fav.analise_estado === "aguarda" ? "⏳ Em fila" : "⚙ Em processamento"}
                    </Link>
                  ) : (
                    <button
                      onClick={() => setConfirmacao(fav)}
                      style={{
                        padding: "10px 20px",
                        background: "#f0f4ea",
                        color: "#607b43",
                        border: "1px solid #607b43",
                        borderRadius: "10px",
                        cursor: "pointer",
                        fontSize: "13px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <><Sparkles size={14} /> Criar análise AI</>
                    </button>
                  )}

                  <button
                    onClick={() => alternarAlertas(fav)}
                    style={{
                      padding: "10px 14px",
                      background: fav.alerta_ativo ? "#f0f4ea" : "white",
                      color: fav.alerta_ativo ? "#607b43" : "#999",
                      border: fav.alerta_ativo ? "1px solid #607b43" : "1px solid #ddd",
                      borderRadius: "10px",
                      cursor: "pointer",
                      fontSize: "13px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                    title={fav.alerta_ativo ? "Desativar alertas" : "Ativar alertas"}
                  >
                    <Bell size={14} />
                    {fav.alerta_ativo ? "Alertas ativos" : "Ativar alertas"}
                  </button>

                  <button
                    onClick={() => removerFavorito(fav)}
                    style={{
                      padding: "10px",
                      background: "white",
                      border: "1px solid #ddd",
                      borderRadius: "10px",
                      cursor: "pointer",
                      fontSize: "13px",
                      color: "#999",
                    }}
                    title="Remover favorito"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <RecommendationList
          filters={filters}
          recommendations={recommendationCards}
          favoriteIds={favoritos.map((fav) => fav.concurso_id)}
          analysisJobs={recommendationAnalysisJobs}
          loading={loading}
        />
          </div>
        </div>

      </main>

      <AnalysisConfirmationModal
        open={confirmacao !== null}
        titulo={confirmacao?.titulo ?? ""}
        entidade={confirmacao?.entidade ?? ""}
        localizacao={confirmacao?.localizacao}
        onClose={() => setConfirmacao(null)}
        onConfirm={async () => {
          if (!confirmacao) return;
          await criarAnalise(confirmacao);
        }}
      />
    </PrivateLayout>
  );
}
