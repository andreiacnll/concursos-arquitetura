"use client";

import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { FileUp, Globe, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { API_URL } from "@/lib/api";
import type { CompanySourceSummary } from "@/components/company/company-types";

type Props = {
  token?: string;
  onChanged?: () => Promise<void> | void;
};

type SourceKind = "portfolio" | "document";

function statusLabel(status?: string) {
  const labels: Record<string, string> = {
    not_added: "Não adicionada",
    processing: "A processar",
    processed: "Processada",
    partial: "Parcial",
    no_results: "Sem resultados",
    error: "Erro",
  };
  return labels[status || ""] ?? status ?? "Desconhecido";
}

function formatDate(value?: string | null) {
  if (!value) return "Sem registo";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-PT", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Não foi possível ler o ficheiro."));
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

export default function ProfileCompanySources({ token, onChanged }: Props) {
  const [sources, setSources] = useState<CompanySourceSummary[]>([]);
  const [website, setWebsite] = useState("");
  const [portfolioFile, setPortfolioFile] = useState<File | null>(null);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchSources = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/company/sources`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error("Não foi possível carregar as fontes.");
      }
      const data = (await response.json()) as {
        sources?: CompanySourceSummary[];
      };
      setSources(Array.isArray(data.sources) ? data.sources : []);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível carregar as fontes.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSources();
  }, [fetchSources]);

  async function afterMutation(message: string) {
    await fetchSources();
    await onChanged?.();
    setSuccess(message);
  }

  async function addWebsite() {
    if (!token) return;
    const url = website.trim();
    if (!url) {
      setError("Introduz o website a adicionar.");
      return;
    }

    setBusyKey("add-website");
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(`${API_URL}/company/website/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ url }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Não foi possível adicionar o website.");
      }
      setWebsite("");
      await afterMutation("Website adicionado e processado.");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível adicionar o website.",
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function addFile(kind: SourceKind) {
    if (!token) return;
    const file = kind === "portfolio" ? portfolioFile : documentFile;
    if (!file) {
      setError("Seleciona um ficheiro para adicionar.");
      return;
    }

    setBusyKey(`add-${kind}`);
    setError(null);
    setSuccess(null);
    try {
      const contentBase64 = await readFileAsBase64(file);
      const response = await fetch(`${API_URL}/company/documents/ingest-file`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          filename: file.name,
          content_base64: contentBase64,
          source_type: kind,
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Não foi possível adicionar o ficheiro.");
      }
      if (kind === "portfolio") {
        setPortfolioFile(null);
      } else {
        setDocumentFile(null);
      }
      await afterMutation("Fonte adicionada e processada.");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível adicionar o ficheiro.",
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function removeSource(source: CompanySourceSummary) {
    if (!token) return;
    setBusyKey(`remove-${source.key}`);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(`${API_URL}/company/sources`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          source_type: source.source_type,
          source: source.source,
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Não foi possível remover a fonte.");
      }
      await afterMutation("Fonte removida.");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível remover a fonte.",
      );
    } finally {
      setBusyKey(null);
    }
  }

  async function reprocessSource(source: CompanySourceSummary) {
    if (!token) return;
    if (source.source_type !== "website") {
      setError(
        "Para reprocessar portfolio ou documentos, adiciona novamente o ficheiro atualizado.",
      );
      return;
    }

    setBusyKey(`reprocess-${source.key}`);
    setError(null);
    setSuccess(null);
    try {
      await removeSource(source);
      setBusyKey(`reprocess-${source.key}`);
      const response = await fetch(`${API_URL}/company/website/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ url: source.source }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Não foi possível reprocessar a fonte.");
      }
      await afterMutation("Fonte reprocessada.");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Não foi possível reprocessar a fonte.",
      );
    } finally {
      setBusyKey(null);
    }
  }

  function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
    kind: SourceKind,
  ) {
    const file = event.target.files?.[0] ?? null;
    if (kind === "portfolio") {
      setPortfolioFile(file);
    } else {
      setDocumentFile(file);
    }
  }

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <div>
          <h2>Fontes</h2>
          <p>Website, portfolio, documentos e histórico de processamento.</p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={fetchSources}
          disabled={loading}
        >
          {loading ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
          Atualizar
        </button>
      </div>

      <div className="profile-card-body">
        <div className="profile-source-add-grid">
          <div className="profile-source-add">
            <label>
              <Globe size={15} />
              Website
            </label>
            <div className="profile-source-input-row">
              <input
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
                placeholder="https://exemplo.pt"
              />
              <button
                type="button"
                className="btn-primary"
                onClick={addWebsite}
                disabled={busyKey === "add-website"}
              >
                <Plus size={15} />
                Adicionar
              </button>
            </div>
          </div>

          <div className="profile-source-add">
            <label>
              <FileUp size={15} />
              Portfolio
            </label>
            <div className="profile-source-input-row">
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(event) => handleFileChange(event, "portfolio")}
              />
              <button
                type="button"
                className="btn-primary"
                onClick={() => addFile("portfolio")}
                disabled={busyKey === "add-portfolio"}
              >
                <Plus size={15} />
                Adicionar
              </button>
            </div>
          </div>

          <div className="profile-source-add">
            <label>
              <FileUp size={15} />
              Documentos
            </label>
            <div className="profile-source-input-row">
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(event) => handleFileChange(event, "document")}
              />
              <button
                type="button"
                className="btn-primary"
                onClick={() => addFile("document")}
                disabled={busyKey === "add-document"}
              >
                <Plus size={15} />
                Adicionar
              </button>
            </div>
          </div>
        </div>

        {error && <div className="profile-form-message error">{error}</div>}
        {success && <div className="profile-form-message success">{success}</div>}

        <div className="profile-sources-table">
          <div className="profile-sources-head">
            <span>Fonte</span>
            <span>Estado</span>
            <span>Última sincronização</span>
            <span>Ações</span>
          </div>
          {sources.length === 0 ? (
            <div className="profile-empty-message">
              Ainda não existem fontes processadas.
            </div>
          ) : (
            sources.map((source) => (
              <div key={source.key} className="profile-sources-row">
                <div>
                  <strong>{source.label}</strong>
                  <span>{source.name}</span>
                  <small>
                    {source.facts_count} factos · {source.projects_count} projetos
                  </small>
                </div>
                <span>{statusLabel(source.status)}</span>
                <span>{formatDate(source.submitted_at)}</span>
                <div className="profile-source-actions">
                  <button
                    type="button"
                    className="profile-icon-button"
                    aria-label={`Reprocessar ${source.name}`}
                    onClick={() => reprocessSource(source)}
                    disabled={busyKey !== null}
                  >
                    <RefreshCw size={16} />
                  </button>
                  <button
                    type="button"
                    className="profile-icon-button danger"
                    aria-label={`Remover ${source.name}`}
                    onClick={() => removeSource(source)}
                    disabled={busyKey !== null}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
