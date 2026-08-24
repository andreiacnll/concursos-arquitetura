"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  PencilLine,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { CompanyCVEntry, CompanyProfile } from "./company-types";

type Props = {
  profile: CompanyProfile;
  onChange: (next: CompanyProfile) => void;
};

const EMPTY: CompanyCVEntry = {
  id: "",
  category: "fact",
  title: "",
  description: "",
  reuse_key: "",
  scope: "company",
  role: "",
  person: "",
  project: "",
  metric: "",
  numeric_value: null,
  unit: "",
  answer: "",
  status: "confirmed",
  source: "manual",
  requirement_ids: [],
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

async function token(): Promise<string> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}

function categoryLabel(value: string): string {
  const normalized = clean(value).toLowerCase();
  if (normalized === "project") return "Projeto";
  if (normalized === "person") return "Pessoa / equipa";
  if (normalized === "training") return "Formação / certificação";
  if (normalized === "experience") return "Experiência";
  if (normalized === "company") return "Empresa";
  return normalized ? clean(value) : "Registo";
}

function scopeLabel(value: string): string {
  const normalized = clean(value).toLowerCase();
  if (normalized === "person") return "Pessoa";
  if (normalized === "project") return "Projeto";
  return "Empresa";
}

export default function CompanyCVSection({ profile, onChange }: Props) {
  const [items, setItems] = useState<CompanyCVEntry[]>(profile.cv || []);
  const [draft, setDraft] = useState<CompanyCVEntry>({ ...EMPTY });
  const [editing, setEditing] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showTechnical, setShowTechnical] = useState(false);

  function sync(next: CompanyCVEntry[]) {
    setItems(next);
    onChange({ ...profile, cv: next });
  }

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const auth = await token();
        if (!auth) return;

        const response = await fetch(`${API_URL}/company/cv?_=${Date.now()}`, {
          cache: "no-store",
          headers: { Authorization: `Bearer ${auth}` },
        });

        if (!response.ok) return;

        const body = await response.json();
        if (!active) return;

        const next = Array.isArray(body?.cv) ? body.cv : [];
        setItems(next);
        onChange({ ...profile, cv: next });
      } catch {
        // O perfil local continua visível se a leitura remota falhar.
      }
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!open || typeof document === "undefined") return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) {
        closeEditor();
      }
    };

    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, saving]);

  const sortedItems = useMemo(
    () =>
      [...items].sort((a, b) =>
        clean(a.title).localeCompare(clean(b.title), "pt"),
      ),
    [items],
  );

  function startNew() {
    setDraft({ ...EMPTY });
    setEditing(null);
    setError("");
    setShowTechnical(false);
    setOpen(true);
  }

  function startEdit(item: CompanyCVEntry) {
    setDraft({ ...item });
    setEditing(item.id);
    setError("");
    setShowTechnical(Boolean(clean(item.reuse_key) || clean(item.metric)));
    setOpen(true);
  }

  function closeEditor() {
    if (saving) return;
    setOpen(false);
    setEditing(null);
    setDraft({ ...EMPTY });
    setError("");
    setShowTechnical(false);
  }

  async function save() {
    if (!draft.title.trim()) {
      setError("Indica um título para o registo.");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const auth = await token();
      if (!auth) throw new Error("Sessão não encontrada.");

      const path = editing
        ? `${API_URL}/company/cv/${encodeURIComponent(editing)}`
        : `${API_URL}/company/cv`;

      const response = await fetch(path, {
        method: editing ? "PUT" : "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth}`,
        },
        body: JSON.stringify({
          ...draft,
          numeric_value:
            draft.numeric_value === null ||
            draft.numeric_value === undefined ||
            draft.numeric_value === ("" as any)
              ? null
              : Number(draft.numeric_value),
          source: editing ? draft.source || "manual" : "manual",
        }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.detail || "Não foi possível guardar o CV.");
      }

      const body = await response.json();
      const saved = body.entry as CompanyCVEntry;

      const next = editing
        ? items.map((item) => (item.id === editing ? saved : item))
        : [...items.filter((item) => item.id !== saved.id), saved];

      sync(next);
      closeEditor();
    } catch (exc) {
      setError(
        exc instanceof Error ? exc.message : "Não foi possível guardar.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: CompanyCVEntry) {
    if (!window.confirm(`Apagar "${item.title}" do CV?`)) return;

    try {
      const auth = await token();
      if (!auth) throw new Error("Sessão não encontrada.");

      const response = await fetch(
        `${API_URL}/company/cv/${encodeURIComponent(item.id)}`,
        {
          method: "DELETE",
          cache: "no-store",
          headers: { Authorization: `Bearer ${auth}` },
        },
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.detail || "Não foi possível apagar.");
      }

      sync(items.filter((candidate) => candidate.id !== item.id));
    } catch (exc) {
      setError(
        exc instanceof Error ? exc.message : "Não foi possível apagar.",
      );
    }
  }

  const modal =
    open && mounted
      ? createPortal(
          <div
            className="cvp-backdrop"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) closeEditor();
            }}
          >
            <section
              className="cvp-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="cvp-title"
            >
              <header className="cvp-modal-head">
                <div>
                  <span>CV DA EMPRESA</span>
                  <h2 id="cvp-title">
                    {editing ? "Editar registo" : "Adicionar registo"}
                  </h2>
                  <p>
                    Este dado fica disponível para comparar automaticamente
                    requisitos de concursos futuros.
                  </p>
                </div>

                <button
                  type="button"
                  className="cvp-icon-button"
                  onClick={closeEditor}
                  disabled={saving}
                  aria-label="Fechar"
                  title="Fechar"
                >
                  <X size={20} />
                </button>
              </header>

              <div className="cvp-modal-body">
                <div className="cvp-grid two">
                  <label>
                    <span>Título *</span>
                    <input
                      autoFocus
                      value={draft.title}
                      onChange={(event) =>
                        setDraft({ ...draft, title: event.target.value })
                      }
                      placeholder="Ex.: Projeto de mercado municipal"
                    />
                  </label>

                  <label>
                    <span>Categoria</span>
                    <select
                      value={draft.category || "fact"}
                      onChange={(event) =>
                        setDraft({ ...draft, category: event.target.value })
                      }
                    >
                      <option value="fact">Outro facto</option>
                      <option value="project">Projeto</option>
                      <option value="person">Pessoa / equipa</option>
                      <option value="experience">Experiência</option>
                      <option value="training">Formação / certificação</option>
                      <option value="company">Empresa</option>
                    </select>
                  </label>
                </div>

                <label>
                  <span>Descrição</span>
                  <textarea
                    rows={3}
                    value={draft.description}
                    onChange={(event) =>
                      setDraft({ ...draft, description: event.target.value })
                    }
                    placeholder="Informação que interessa para avaliar concursos."
                  />
                </label>

                <div className="cvp-grid two">
                  <label>
                    <span>Âmbito</span>
                    <select
                      value={draft.scope || "company"}
                      onChange={(event) =>
                        setDraft({ ...draft, scope: event.target.value })
                      }
                    >
                      <option value="company">Empresa</option>
                      <option value="person">Pessoa</option>
                      <option value="project">Projeto</option>
                    </select>
                  </label>

                  <label>
                    <span>Função / papel</span>
                    <input
                      value={draft.role}
                      onChange={(event) =>
                        setDraft({ ...draft, role: event.target.value })
                      }
                      placeholder="Ex.: Coordenador de projeto"
                    />
                  </label>
                </div>

                {draft.scope === "person" ? (
                  <label>
                    <span>Pessoa</span>
                    <input
                      value={draft.person}
                      onChange={(event) =>
                        setDraft({ ...draft, person: event.target.value })
                      }
                      placeholder="Nome do elemento da equipa"
                    />
                  </label>
                ) : null}

                {draft.scope === "project" ? (
                  <label>
                    <span>Projeto</span>
                    <input
                      value={draft.project}
                      onChange={(event) =>
                        setDraft({ ...draft, project: event.target.value })
                      }
                      placeholder="Nome do projeto de referência"
                    />
                  </label>
                ) : null}

                <div className="cvp-grid value">
                  <label>
                    <span>Valor real</span>
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={
                        draft.numeric_value === null ||
                        draft.numeric_value === undefined
                          ? ""
                          : String(draft.numeric_value)
                      }
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          numeric_value:
                            event.target.value === ""
                              ? null
                              : Number(event.target.value),
                        })
                      }
                      placeholder="Ex.: 15"
                    />
                  </label>

                  <label>
                    <span>Unidade</span>
                    <input
                      value={draft.unit}
                      onChange={(event) =>
                        setDraft({ ...draft, unit: event.target.value })
                      }
                      placeholder="anos, €, m², h..."
                    />
                  </label>
                </div>

                <button
                  type="button"
                  className="cvp-technical-toggle"
                  onClick={() => setShowTechnical((value) => !value)}
                >
                  {showTechnical
                    ? "Ocultar campos técnicos"
                    : "Mostrar campos técnicos"}
                </button>

                {showTechnical ? (
                  <div className="cvp-technical">
                    <div className="cvp-grid two">
                      <label>
                        <span>Métrica</span>
                        <input
                          value={draft.metric}
                          onChange={(event) =>
                            setDraft({ ...draft, metric: event.target.value })
                          }
                          placeholder="Ex.: years, project_value_eur"
                        />
                      </label>

                      <label>
                        <span>Estado</span>
                        <select
                          value={draft.status || "confirmed"}
                          onChange={(event) =>
                            setDraft({ ...draft, status: event.target.value })
                          }
                        >
                          <option value="confirmed">Confirmado</option>
                          <option value="pending">Por confirmar</option>
                        </select>
                      </label>
                    </div>

                    <label>
                      <span>Chave reutilizável</span>
                      <input
                        value={draft.reuse_key}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            reuse_key: event.target.value,
                          })
                        }
                        placeholder="Deixa vazio para ser gerada automaticamente"
                      />
                    </label>
                  </div>
                ) : null}

                {error ? (
                  <p className="cvp-error" role="alert">
                    {error}
                  </p>
                ) : null}
              </div>

              <footer className="cvp-modal-footer">
                <button
                  type="button"
                  className="cvp-cancel"
                  onClick={closeEditor}
                  disabled={saving}
                >
                  Cancelar
                </button>

                <button
                  type="button"
                  className="cvp-save"
                  onClick={save}
                  disabled={saving}
                >
                  <Save size={16} />
                  {saving
                    ? "A guardar..."
                    : editing
                      ? "Guardar alterações"
                      : "Adicionar ao CV"}
                </button>
              </footer>
            </section>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <section className="cvp-section">
        <div className="cvp-head">
          <div>
            <span className="cvp-kicker">CV DA EMPRESA</span>
            <h2>Factos reutilizáveis para análise de concursos</h2>
            <p>
              Pessoas, projetos, experiência, formação e outros dados que o
              sistema pode reutilizar automaticamente.
            </p>
          </div>

          <button type="button" className="cvp-add" onClick={startNew}>
            <Plus size={17} />
            Adicionar registo
          </button>
        </div>

        {error && !open ? (
          <p className="cvp-error" role="alert">
            {error}
          </p>
        ) : null}

        {sortedItems.length ? (
          <div className="cvp-list">
            {sortedItems.map((item) => {
              const meta = [
                categoryLabel(item.category),
                scopeLabel(item.scope),
                clean(item.person),
                clean(item.project),
                item.numeric_value !== null &&
                item.numeric_value !== undefined
                  ? `${item.numeric_value}${item.unit ? ` ${item.unit}` : ""}`
                  : "",
              ].filter(Boolean);

              return (
                <article className="cvp-item" key={item.id || item.reuse_key}>
                  <div className="cvp-item-copy">
                    <strong>{clean(item.title) || "Registo de CV"}</strong>
                    {clean(item.description) ? (
                      <p>{clean(item.description)}</p>
                    ) : null}
                    <div className="cvp-meta">
                      {meta.map((value, index) => (
                        <span key={`${value}-${index}`}>{value}</span>
                      ))}
                    </div>
                  </div>

                  <div className="cvp-actions">
                    <button
                      type="button"
                      className="cvp-action"
                      onClick={() => startEdit(item)}
                      title="Editar"
                      aria-label={`Editar ${item.title}`}
                    >
                      <PencilLine size={16} />
                      <span>Editar</span>
                    </button>

                    <button
                      type="button"
                      className="cvp-action danger"
                      onClick={() => remove(item)}
                      title="Apagar"
                      aria-label={`Apagar ${item.title}`}
                    >
                      <Trash2 size={16} />
                      <span>Apagar</span>
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="cvp-empty">
            <strong>Ainda não existem registos no CV.</strong>
            <p>
              Adiciona apenas informação que possa ser reutilizada na avaliação
              de concursos.
            </p>
            <button type="button" className="cvp-empty-add" onClick={startNew}>
              <Plus size={16} />
              Adicionar primeiro registo
            </button>
          </div>
        )}
      </section>

      {modal}

      <style jsx global>{`
        .cvp-section {
          background: #fff;
          border: 1px solid #e6e7e1;
          border-radius: 18px;
          padding: 24px;
        }

        .cvp-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 24px;
          margin-bottom: 20px;
        }

        .cvp-kicker,
        .cvp-modal-head span {
          color: #6b7f45;
          font-size: 10px;
          line-height: 1.2;
          font-weight: 800;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .cvp-head h2 {
          margin: 6px 0 6px;
          font-size: 20px;
          line-height: 1.25;
        }

        .cvp-head p,
        .cvp-modal-head p {
          margin: 0;
          color: #777b73;
          font-size: 13px;
          line-height: 1.5;
        }

        .cvp-add,
        .cvp-empty-add,
        .cvp-save {
          border: 0;
          border-radius: 10px;
          background: #607b43;
          color: #fff;
          min-height: 40px;
          padding: 0 14px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          white-space: nowrap;
        }

        .cvp-add:hover,
        .cvp-empty-add:hover,
        .cvp-save:hover {
          background: #526b39;
        }

        .cvp-list {
          display: grid;
          gap: 10px;
        }

        .cvp-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 18px;
          padding: 15px 16px;
          border: 1px solid #e7e8e2;
          border-radius: 12px;
          background: #fcfcfa;
        }

        .cvp-item-copy {
          min-width: 0;
        }

        .cvp-item-copy > strong {
          display: block;
          font-size: 14px;
          line-height: 1.35;
          color: #20221f;
        }

        .cvp-item-copy > p {
          margin: 5px 0 0;
          color: #71756e;
          font-size: 12px;
          line-height: 1.45;
        }

        .cvp-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 9px;
        }

        .cvp-meta span {
          border-radius: 999px;
          background: #f0f3eb;
          color: #687254;
          padding: 4px 8px;
          font-size: 10px;
          line-height: 1;
        }

        .cvp-actions {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          flex: 0 0 auto;
        }

        .cvp-action {
          min-height: 34px;
          border: 1px solid #dfe1da;
          border-radius: 9px;
          background: #fff;
          color: #53584f;
          padding: 0 10px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 650;
          cursor: pointer;
        }

        .cvp-action:hover {
          border-color: #bfc7b4;
          background: #f8faf5;
          color: #536b3c;
        }

        .cvp-action.danger {
          color: #995146;
        }

        .cvp-action.danger:hover {
          border-color: #e2beb7;
          background: #fff7f5;
          color: #8d3f35;
        }

        .cvp-empty {
          border: 1px dashed #d9ddd2;
          border-radius: 12px;
          padding: 24px;
          text-align: center;
          background: #fbfcf9;
        }

        .cvp-empty strong {
          font-size: 14px;
        }

        .cvp-empty p {
          margin: 6px auto 14px;
          max-width: 560px;
          color: #777b73;
          font-size: 12px;
        }

        .cvp-backdrop {
          position: fixed;
          inset: 0;
          z-index: 3000;
          display: grid;
          place-items: center;
          padding: 24px;
          background: rgba(25, 28, 22, 0.42);
          backdrop-filter: blur(3px);
        }

        .cvp-modal {
          width: min(760px, 100%);
          max-height: min(820px, calc(100vh - 48px));
          display: flex;
          flex-direction: column;
          overflow: hidden;
          border-radius: 18px;
          background: #fff;
          border: 1px solid #dedfd9;
          box-shadow: 0 28px 80px rgba(27, 31, 24, 0.22);
        }

        .cvp-modal-head {
          display: flex;
          justify-content: space-between;
          gap: 18px;
          padding: 22px 24px 18px;
          border-bottom: 1px solid #ecece7;
        }

        .cvp-modal-head h2 {
          margin: 5px 0 6px;
          font-size: 22px;
          line-height: 1.2;
        }

        .cvp-icon-button {
          width: 36px;
          height: 36px;
          border: 1px solid #e2e3dd;
          border-radius: 9px;
          background: #fff;
          color: #555a52;
          display: grid;
          place-items: center;
          cursor: pointer;
          flex: 0 0 auto;
        }

        .cvp-modal-body {
          overflow-y: auto;
          display: grid;
          gap: 15px;
          padding: 20px 24px 24px;
        }

        .cvp-modal-body label {
          display: grid;
          gap: 6px;
          min-width: 0;
        }

        .cvp-modal-body label > span {
          color: #555b52;
          font-size: 11px;
          font-weight: 700;
        }

        .cvp-modal-body input,
        .cvp-modal-body textarea,
        .cvp-modal-body select {
          width: 100%;
          min-width: 0;
          border: 1px solid #dfe1da;
          border-radius: 9px;
          background: #fff;
          color: #22251f;
          padding: 10px 11px;
          font: inherit;
          font-size: 13px;
          outline: none;
        }

        .cvp-modal-body input,
        .cvp-modal-body select {
          min-height: 40px;
        }

        .cvp-modal-body textarea {
          resize: vertical;
        }

        .cvp-modal-body input:focus,
        .cvp-modal-body textarea:focus,
        .cvp-modal-body select:focus {
          border-color: #809863;
          box-shadow: 0 0 0 3px rgba(96, 123, 67, 0.1);
        }

        .cvp-grid {
          display: grid;
          gap: 14px;
        }

        .cvp-grid.two {
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        }

        .cvp-grid.value {
          grid-template-columns: minmax(0, 1fr) 160px;
        }

        .cvp-technical-toggle {
          justify-self: start;
          border: 0;
          background: transparent;
          padding: 2px 0;
          color: #64774a;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
        }

        .cvp-technical {
          display: grid;
          gap: 14px;
          padding: 14px;
          border-radius: 11px;
          background: #f7f8f4;
          border: 1px solid #e6e8df;
        }

        .cvp-error {
          margin: 0;
          border-radius: 9px;
          padding: 10px 12px;
          background: #fff2f0;
          color: #993f35;
          font-size: 12px;
          line-height: 1.4;
        }

        .cvp-modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 9px;
          padding: 15px 24px;
          border-top: 1px solid #ecece7;
          background: #fbfbf9;
        }

        .cvp-cancel {
          min-height: 40px;
          border: 1px solid #dfe1da;
          border-radius: 10px;
          background: #fff;
          color: #555a52;
          padding: 0 14px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
        }

        .cvp-save:disabled,
        .cvp-cancel:disabled,
        .cvp-icon-button:disabled {
          opacity: 0.5;
          cursor: default;
        }

        @media (max-width: 720px) {
          .cvp-head,
          .cvp-item {
            align-items: stretch;
            flex-direction: column;
          }

          .cvp-add {
            width: 100%;
          }

          .cvp-actions {
            width: 100%;
          }

          .cvp-action {
            flex: 1;
            justify-content: center;
          }

          .cvp-backdrop {
            padding: 12px;
          }

          .cvp-modal {
            max-height: calc(100vh - 24px);
          }

          .cvp-grid.two,
          .cvp-grid.value {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </>
  );
}
