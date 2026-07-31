"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, AlertCircle, Lightbulb, ArrowRight } from "lucide-react";
import RecommendationCompetitionCard from "./RecommendationCompetitionCard";
import type { RecommendationCard as RecommendationCardType } from "./recommendation-types";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

type LoadingState = "idle" | "loading" | "success" | "error";

export default function RecommendationList() {
  const [recommendations, setRecommendations] = useState<RecommendationCardType[]>([]);
  const [state, setState] = useState<LoadingState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set());
  const { session } = useAuth();

  const fetchRecommendations = useCallback(async () => {
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
            : `Erro ao carregar recomendações (${response.status})`
        );
      }

      const data = await response.json();
      const list = Array.isArray(data) ? data : [];

      setRecommendations(list);
      setState("success");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Ocorreu um erro inesperado.";
      setErrorMessage(message);
      setState("error");
    }
  }, [session?.access_token]);

  // Fetch favorites
  const fetchFavorites = useCallback(async () => {
    const token = session?.access_token;
    if (!token) return;

    try {
      const response = await fetch(`${API_URL}/favoritos`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) return;

      const data = await response.json();
      const ids = (data.favoritos ?? []).map(
        (f: { concurso_id: number }) => f.concurso_id
      );
      setFavoriteIds(new Set(ids));
    } catch {
      // Silently fail for favorites
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (session?.access_token) {
      fetchRecommendations();
      fetchFavorites();
    }
  }, [session?.access_token, fetchRecommendations, fetchFavorites]);

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
      // Revert on failure
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

  // -- Not authenticated --
  if (!session?.access_token) {
    return null;
  }

  // -- Loading --
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

  // -- Error --
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

  // -- Empty --
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

  // -- Success --
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
        Concursos identificados como oportunidades com base no perfil, experiência
        e competências da empresa.
      </p>
      <div className="competition-grid">
        {recommendations.map((rec) => (
          <RecommendationCompetitionCard
            key={rec.competition_id}
            recommendation={rec}
            index={rec.competition_id}
            isFavorite={favoriteIds.has(rec.competition_id)}
            onToggleFavorite={() => toggleFavorite(rec.competition_id)}
          />
        ))}
      </div>
    </section>
  );
}
