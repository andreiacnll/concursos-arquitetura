"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowRight, Lightbulb, RefreshCw } from "lucide-react";
import RecommendationCompetitionCard from "./RecommendationCompetitionCard";
import type { RecommendationCard as RecommendationCardType } from "./recommendation-types";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  ANALYSIS_POLL_INTERVAL_MS,
  fetchAnalysisJobState,
  isActiveAnalysisStatus,
  normalizeAnalysisJob,
  type AnalysisJobState,
} from "@/lib/analysis-jobs";
import {
  getCompetitionDeadline,
  getCompetitionValue,
  matchesCompetitionFilters,
  parseFilterDate,
  type CompetitionFiltersState,
} from "@/components/competition-filters";

type LoadingState = "idle" | "loading" | "success" | "error";
type RecommendationSort = "score" | "preco" | "prazo" | "data";

function recommendationToFilterItem(recommendation: RecommendationCardType) {
  return {
    titulo: recommendation.title,
    entidade: recommendation.entity ?? null,
    distrito: recommendation.location ?? null,
    municipio: recommendation.location ?? null,
    preco_base: recommendation.base_price ?? null,
    data_limite: recommendation.deadline ?? null,
    data_entrega_propostas: recommendation.deadline ?? null,
    data_fim_calculada: recommendation.deadline ?? null,
    data_publicacao_iso: recommendation.published_at ?? null,
    data: recommendation.published_at ?? null,
    tipo_procedimento: recommendation.procedure_type ?? null,
  };
}

function isRecommendationAvailable(recommendation: RecommendationCardType) {
  const deadline = getCompetitionDeadline(
    recommendationToFilterItem(recommendation),
  );
  if (!deadline) return false;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return deadline >= today;
}

function compareRecommendations(
  a: RecommendationCardType,
  b: RecommendationCardType,
  sortBy: RecommendationSort,
) {
  if (sortBy === "score") {
    return (b.compatibility_score ?? -1) - (a.compatibility_score ?? -1);
  }

  if (sortBy === "preco") {
    const aValue = getCompetitionValue(recommendationToFilterItem(a));
    const bValue = getCompetitionValue(recommendationToFilterItem(b));
    if (aValue === null) return bValue === null ? 0 : 1;
    if (bValue === null) return -1;
    return bValue - aValue;
  }

  if (sortBy === "prazo") {
    const aTime = getCompetitionDeadline(
      recommendationToFilterItem(a),
    )?.getTime();
    const bTime = getCompetitionDeadline(
      recommendationToFilterItem(b),
    )?.getTime();
    if (aTime === undefined) return bTime === undefined ? 0 : 1;
    if (bTime === undefined) return -1;
    return aTime - bTime;
  }

  const aTime = parseFilterDate(a.published_at ?? null)?.getTime() ?? 0;
  const bTime = parseFilterDate(b.published_at ?? null)?.getTime() ?? 0;
  return bTime - aTime;
}

type RecommendationListProps = {
  filters?: CompetitionFiltersState;
  recommendations?: RecommendationCardType[];
  favoriteIds?: number[];
  analysisJobs?: Record<number, AnalysisJobState>;
  loading?: boolean;
};

export default function RecommendationList({
  filters,
  recommendations: providedRecommendations,
  favoriteIds: providedFavoriteIds,
  analysisJobs: providedAnalysisJobs,
  loading: providedLoading = false,
}: RecommendationListProps) {
  const receivesRecommendations = providedRecommendations !== undefined;
  const receivesFavoriteIds = providedFavoriteIds !== undefined;
  const receivesAnalysisJobs = providedAnalysisJobs !== undefined;
  const [recommendations, setRecommendations] = useState<RecommendationCardType[]>(
    providedRecommendations ?? [],
  );
  const [state, setState] = useState<LoadingState>(
    providedLoading ? "loading" : receivesRecommendations ? "success" : "idle",
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(
    () => new Set(providedFavoriteIds ?? []),
  );
  const [sortBy, setSortBy] = useState<RecommendationSort>("score");
  const [onlyScore50, setOnlyScore50] = useState(true);
  const [analysisJobsMap, setAnalysisJobsMap] = useState<Record<number, AnalysisJobState>>(
    providedAnalysisJobs ?? {},
  );
  const { session } = useAuth();

  const fetchRecommendations = useCallback(async () => {
    if (receivesRecommendations) return;

    const token = session?.access_token;
    if (!token) {
      setState("idle");
      return;
    }

    setState("loading");
    setErrorMessage(null);

    try {
      const response = await fetch(`${API_URL}/company/recommendation-cards`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Sessão expirada. Inicia sessão novamente."
            : `Erro ao carregar recomendações (${response.status})`,
        );
      }

      const data = await response.json();
      setRecommendations(Array.isArray(data) ? data : []);
      setState("success");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Ocorreu um erro inesperado.";
      setErrorMessage(message);
      setState("error");
    }
  }, [receivesRecommendations, session?.access_token]);

  const fetchFavorites = useCallback(async () => {
    if (receivesFavoriteIds) return;

    const token = session?.access_token;
    if (!token) return;

    try {
      const response = await fetch(`${API_URL}/favoritos`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) return;

      const data = await response.json();
      const ids = (data.favoritos ?? []).map(
        (f: { concurso_id: number }) => f.concurso_id,
      );
      setFavoriteIds(new Set(ids));
    } catch {
      // Favorite state is helpful, but recommendations can render without it.
    }
  }, [receivesFavoriteIds, session?.access_token]);

  const fetchAnalyses = useCallback(async () => {
    if (receivesAnalysisJobs) return;

    const token = session?.access_token;
    if (!token) return;
    try {
      const response = await fetch(`${API_URL}/analises`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json();
      const map: Record<number, AnalysisJobState> = {};
      for (const item of data.analises ?? []) {
        const job = normalizeAnalysisJob(item);
        if (job) map[job.concurso_id] = job;
      }
      setAnalysisJobsMap(map);
    } catch {
      // Analysis state is reconciled best-effort.
    }
  }, [receivesAnalysisJobs, session?.access_token]);

  useEffect(() => {
    if (providedRecommendations === undefined) return;
    setRecommendations(providedRecommendations);
    setState(providedLoading ? "loading" : "success");
    setErrorMessage(null);
  }, [providedLoading, providedRecommendations]);

  useEffect(() => {
    if (providedFavoriteIds === undefined) return;
    setFavoriteIds(new Set(providedFavoriteIds));
  }, [providedFavoriteIds]);

  useEffect(() => {
    if (providedAnalysisJobs === undefined) return;
    setAnalysisJobsMap(providedAnalysisJobs);
  }, [providedAnalysisJobs]);

  useEffect(() => {
    if (session?.access_token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      fetchRecommendations();
      fetchFavorites();
      fetchAnalyses();
    }
  }, [session?.access_token, fetchRecommendations, fetchFavorites, fetchAnalyses]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;
    const active = Object.values(analysisJobsMap).filter((job) =>
      isActiveAnalysisStatus(job.status),
    );
    if (active.length === 0) return;

    const timer = window.setInterval(() => {
      active.forEach((job) => {
        fetchAnalysisJobState(token, job.job_id)
          .then((state) => {
            setAnalysisJobsMap((current) => ({
              ...current,
              [state.concurso_id]: state,
            }));
          })
          .catch(() => {});
      });
    }, ANALYSIS_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [analysisJobsMap, session?.access_token]);

  const visibleRecommendations = useMemo(() => {
    const deduped = Array.from(
      recommendations
        .reduce((map, recommendation) => {
          map.set(recommendation.competition_id, recommendation);
          return map;
        }, new Map<number, RecommendationCardType>())
        .values(),
    );

    return deduped
      .filter(isRecommendationAvailable)
      .filter((recommendation) =>
        filters
          ? matchesCompetitionFilters(
              recommendationToFilterItem(recommendation),
              filters,
            )
          : true,
      )
      .filter(
        (recommendation) =>
          !onlyScore50 ||
          (typeof recommendation.compatibility_score === "number" &&
            recommendation.compatibility_score >= 50),
      )
      .sort((a, b) => compareRecommendations(a, b, sortBy));
  }, [filters, onlyScore50, recommendations, sortBy]);

  function toggleFavorite(competitionId: number) {
    const token = session?.access_token;
    if (!token) return;

    const isAdding = !favoriteIds.has(competitionId);

    setFavoriteIds((prev) => {
      const next = new Set(prev);
      if (isAdding) {
        next.add(competitionId);
      } else {
        next.delete(competitionId);
      }
      return next;
    });

    fetch(`${API_URL}/favoritos/${competitionId}`, {
      method: isAdding ? "POST" : "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (isAdding) {
          next.delete(competitionId);
        } else {
          next.add(competitionId);
        }
        return next;
      });
    });
  }

  async function createAnalysis(competitionId: number) {
    const token = session?.access_token;
    if (!token) return;
    const response = await fetch(`${API_URL}/analises/criar`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ concurso_id: competitionId }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || "Não foi possível criar a análise.");
    }
    const job = normalizeAnalysisJob(await response.json());
    if (job) {
      setAnalysisJobsMap((current) => ({
        ...current,
        [job.concurso_id]: job,
      }));
    }
  }

  if (!session?.access_token) {
    return null;
  }

  if (state === "loading") {
    return (
      <section className="recommendations-section">
        <div className="recommendations-header">
          <div className="recommendations-title-row">
            <Lightbulb size={22} />
            <h2>Recomendados para a empresa</h2>
          </div>
          <span className="rec-badge">AI</span>
        </div>
        <div className="recommendations-loading">
          <div className="rec-loading-spinner" />
          <p>A analisar o perfil da empresa e a encontrar oportunidades alinhadas...</p>
        </div>
      </section>
    );
  }

  if (state === "error") {
    return (
      <section className="recommendations-section">
        <div className="recommendations-header">
          <div className="recommendations-title-row">
            <Lightbulb size={22} />
            <h2>Recomendados para a empresa</h2>
          </div>
          <span className="rec-badge">AI</span>
        </div>
        <div className="recommendations-error">
          <AlertCircle size={36} />
          <h3>Não foi possível carregar as recomendações</h3>
          <p>{errorMessage}</p>
          <button
            type="button"
            className="rec-retry-button"
            onClick={fetchRecommendations}
          >
            <RefreshCw size={15} />
            Tentar novamente
          </button>
        </div>
      </section>
    );
  }

  if (state === "success" && recommendations.length === 0) {
    return (
      <section className="recommendations-section">
        <div className="recommendations-header">
          <div className="recommendations-title-row">
            <Lightbulb size={22} />
            <h2>Recomendados para a empresa</h2>
          </div>
          <span className="rec-badge">AI</span>
        </div>
        <div className="recommendations-empty">
          <Lightbulb size={36} />
          <h3>Ainda não há recomendações</h3>
          <p>
            Completa o perfil da empresa para receberes sugestões de concursos
            alinhados com a vossa experiência e competências.
          </p>
          <a href="/perfil" className="rec-profile-link">
            <ArrowRight size={15} />
            Ir para o perfil
          </a>
        </div>
      </section>
    );
  }

  return (
    <section className="recommendations-section">
      <div className="recommendations-header">
        <div className="recommendations-title-row">
          <Lightbulb size={22} />
          <h2>Recomendados para a empresa</h2>
        </div>
        <div className="recommendations-header-actions">
          <span className="rec-badge">AI</span>
          <button
            type="button"
            className="rec-refresh-button"
            onClick={fetchRecommendations}
            title="Atualizar recomendações"
            aria-label="Atualizar recomendações"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      <p className="recommendations-subtitle">
        Concursos ativos identificados como oportunidades com base no perfil,
        experiência e competências da empresa.
      </p>

      <div className="recommendations-controls">
        <fieldset>
          <legend>Ordenar por</legend>
          {[
            ["score", "Score"],
            ["preco", "Preço"],
            ["prazo", "Prazo"],
            ["data", "Data publicação"],
          ].map(([value, label]) => (
            <label key={value} className="recommendations-radio">
              <input
                type="radio"
                name="recommendation-sort"
                value={value}
                checked={sortBy === value}
                onChange={() => setSortBy(value as RecommendationSort)}
              />
              <span>{label}</span>
            </label>
          ))}
        </fieldset>

        <label className="recommendations-checkbox">
          <input
            type="checkbox"
            checked={onlyScore50}
            onChange={(event) => setOnlyScore50(event.target.checked)}
          />
          <span>Apenas score &gt;= 50</span>
        </label>
      </div>

      <p className="recommendations-subtitle">
        {visibleRecommendations.length} recomendado
        {visibleRecommendations.length === 1 ? "" : "s"} encontrado
        {visibleRecommendations.length === 1 ? "" : "s"}.
      </p>

      {visibleRecommendations.length === 0 ? (
        <div className="recommendations-empty">
          <Lightbulb size={36} />
          <h3>Sem recomendados para estes filtros</h3>
          <p>Altera os filtros ou desativa o limite mínimo de score.</p>
        </div>
      ) : (
        <div className="competition-grid">
          {visibleRecommendations.map((rec) => (
            <RecommendationCompetitionCard
              key={rec.competition_id}
              recommendation={rec}
              index={rec.competition_id}
              isFavorite={favoriteIds.has(rec.competition_id)}
              onToggleFavorite={() => toggleFavorite(rec.competition_id)}
              analysisState={analysisJobsMap[rec.competition_id] ?? null}
              onCreateAnalysis={() => createAnalysis(rec.competition_id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
