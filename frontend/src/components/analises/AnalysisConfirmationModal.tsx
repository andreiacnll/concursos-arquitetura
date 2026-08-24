"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import {
  Building2,
  Clock3,
  ListChecks,
  Loader2,
  MapPin,
  Sparkles,
  X,
} from "lucide-react";

type Props = {
  open: boolean;
  titulo: string;
  entidade: string;
  localizacao?: string | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

export default function AnalysisConfirmationModal({
  open,
  titulo,
  entidade,
  localizacao,
  onClose,
  onConfirm,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submitting) {
        setError(null);
        onClose();
      }
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose, submitting]);

  if (!open) return null;

  function closeModal() {
    setError(null);
    onClose();
  }

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);

    try {
      await onConfirm();
      closeModal();
    } catch (erro) {
      setError(
        erro instanceof Error
          ? erro.message
          : "Não foi possível colocar a análise na fila.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return createPortal(
    <div
      className="analise-confirm-overlay"
      onClick={() => !submitting && closeModal()}
    >
      <div
        className="analise-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analise-confirm-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="analise-confirm-close"
          onClick={closeModal}
          disabled={submitting}
          aria-label="Fechar"
        >
          <X size={18} />
        </button>

        <div className="analise-confirm-icon">
          <Sparkles size={30} />
        </div>

        <h3 id="analise-confirm-title">Criar análise AI?</h3>
        <p>
          A análise AI irá recolher os documentos oficiais disponíveis na
          fonte do concurso e gerar uma análise CNLL atualizada.
        </p>

        <div className="analise-confirm-detail">
          <strong>{titulo}</strong>
          <span>
            <Building2 size={15} />
            {entidade}
          </span>
          {localizacao && (
            <span>
              <MapPin size={15} />
              {localizacao}
            </span>
          )}
        </div>

        <div className="analise-confirm-notice">
          <span>
            <Clock3 size={16} />
            O processo não é instantâneo.
          </span>
          <span>
            <ListChecks size={16} />
            A análise será colocada numa fila.
          </span>
          <span>
            Podes acompanhar o estado em <strong>/analises</strong>.
          </span>
        </div>

        {error && (
          <p className="analise-confirm-error" role="alert">
            {error}
          </p>
        )}

        <div className="analise-confirm-actions">
          <button
            type="button"
            className="analise-confirm-btn secondary"
            onClick={closeModal}
            disabled={submitting}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="analise-confirm-btn primary"
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="spin" size={16} /> A colocar na fila...
              </>
            ) : (
              <>
                <Sparkles size={16} /> Criar análise AI
              </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
