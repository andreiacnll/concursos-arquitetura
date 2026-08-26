"use client";

import { useEffect, useMemo, useRef } from "react";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { compactText } from "@/components/analise/functionalProgramModel";

type ModalSection = {
  key: string;
  title: string;
  items: any[];
  calculatedTotalLabel?: string;
};

type Props = {
  open: boolean;
  title: string;
  summary: string;
  interventionType?: string;
  sections: ModalSection[];
  activeSection?: string | null;
  onClose: () => void;
};

export default function FunctionalProgramModal({
  open,
  title,
  summary,
  interventionType,
  sections,
  activeSection,
  onClose,
}: Props) {
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !activeSection) return;
    sectionRefs.current[activeSection]?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [activeSection, open]);

  const safeSections = useMemo(
    () => sections.filter((section) => section.items.length > 0),
    [sections],
  );

  if (!open) return null;

  return (
    <div
      className="fp-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Programa funcional completo"
    >
      <button
        type="button"
        className="fp-modal-backdrop"
        onClick={onClose}
        aria-label="Fechar modal"
      />
      <div className="fp-modal-panel">
        <header className="fp-modal-header">
          <div>
            <span className="fp-modal-kicker">Programa funcional</span>
            <h3>{title}</h3>
            {interventionType ? <p>{interventionType}</p> : null}
          </div>
          <button
            type="button"
            className="fp-modal-close"
            onClick={onClose}
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </header>

        <div className="fp-modal-summary">
          <span>Leitura arquitetónica do programa</span>
          <p>{summary || "Por confirmar"}</p>
        </div>

        <div className="fp-modal-grid">
          {safeSections.map((section) => (
            <section
              key={section.key}
              className={
                section.key === "area-schedule"
                  ? "fp-modal-section fp-table-section"
                  : "fp-modal-section"
              }
              ref={(node) => {
                sectionRefs.current[section.key] = node;
              }}
            >
              <h4>{section.title}</h4>
              {section.key === "area-schedule" ? (
                <>
                  <div className="fp-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Espaço</th>
                          <th>Quantidade</th>
                          <th>Área unitária</th>
                          <th>Área total</th>
                          <th>Grupo funcional</th>
                        </tr>
                      </thead>
                      <tbody>
                        {section.items.map((item, index) => (
                          <tr key={`${item.label}-${index}`}>
                            <td>{item.label}</td>
                            <td>{item.quantityLabel || "—"}</td>
                            <td>{item.unitAreaLabel || "—"}</td>
                            <td>{item.totalAreaLabel || "Por confirmar"}</td>
                            <td>{item.functionalGroup || "Outros espaços"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {section.calculatedTotalLabel ? (
                    <p className="fp-calculated-total">
                      <span>Total calculado a partir das linhas reconstruídas</span>
                      <strong>{section.calculatedTotalLabel}</strong>
                    </p>
                  ) : null}
                </>
              ) : (
                <ul>
                  {section.items.map((item, index) => (
                    <li key={`${section.key}-${index}`}>
                      {renderSectionItem(item)}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </div>

      <style jsx>{`
        .fp-modal {
          position: fixed;
          inset: 0;
          z-index: 80;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }

        .fp-modal-backdrop {
          position: absolute;
          inset: 0;
          border: 0;
          background: rgba(23, 25, 21, 0.56);
        }

        .fp-modal-panel {
          position: relative;
          z-index: 1;
          width: min(1180px, 100%);
          max-height: min(90vh, 960px);
          overflow: auto;
          border-radius: 18px;
          border: 1px solid #dcded4;
          background: #fff;
          box-shadow: 0 28px 80px rgba(17, 18, 15, 0.2);
          padding: 22px;
        }

        .fp-modal-header {
          display: flex;
          align-items: start;
          justify-content: space-between;
          gap: 16px;
        }

        .fp-modal-kicker {
          display: inline-flex;
          margin-bottom: 6px;
          color: #72814f;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .fp-modal-header h3 {
          margin: 0;
          font-size: clamp(22px, 2.4vw, 30px);
          line-height: 1.08;
        }

        .fp-modal-header p {
          margin: 6px 0 0;
          color: #5f645c;
          font-size: 13px;
        }

        .fp-modal-close {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 38px;
          height: 38px;
          border-radius: 999px;
          border: 1px solid #d8dbcf;
          background: #fff;
          color: #2f332d;
          cursor: pointer;
        }

        .fp-modal-summary {
          margin-top: 18px;
          padding: 18px;
          border: 1px solid #e3e4da;
          border-radius: 16px;
          background: #fbfbf8;
        }

        .fp-modal-summary span {
          display: inline-flex;
          margin-bottom: 7px;
          color: #6f7369;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .fp-modal-summary p {
          margin: 0;
          color: #242822;
          font-size: 14px;
          line-height: 1.7;
        }

        .fp-modal-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
          margin-top: 16px;
        }

        .fp-modal-section {
          padding: 16px;
          border: 1px solid #e4e6dc;
          border-radius: 16px;
          background: #fff;
        }

        .fp-table-section {
          grid-column: 1 / -1;
        }

        .fp-modal-section h4 {
          margin: 0 0 10px;
          font-size: 15px;
        }

        .fp-modal-section ul {
          margin: 0;
          padding-left: 18px;
          color: #2b2f28;
          line-height: 1.6;
        }

        .fp-modal-section li + li {
          margin-top: 8px;
        }

        .fp-table-wrap {
          overflow-x: auto;
          border: 1px solid #e5e6df;
          border-radius: 12px;
        }

        table {
          width: 100%;
          border-collapse: collapse;
          min-width: 860px;
          font-size: 13px;
        }

        th,
        td {
          padding: 11px 13px;
          border-bottom: 1px solid #ecece7;
          text-align: left;
          vertical-align: top;
        }

        th {
          background: #f7f8f3;
          color: #676d62;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        td:first-child {
          font-weight: 700;
        }

        .fp-calculated-total {
          display: flex;
          justify-content: space-between;
          gap: 20px;
          margin: 12px 0 0;
          padding: 12px 14px;
          border-radius: 10px;
          background: #f7f8f3;
          font-size: 12px;
        }

        @media (max-width: 900px) {
          .fp-modal {
            padding: 12px;
          }

          .fp-modal-panel {
            max-height: 92vh;
            padding: 18px;
          }

          .fp-modal-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}

function renderSectionItem(item: any): ReactNode {
  if (item === null || item === undefined || item === "") return "Por confirmar";
  if (typeof item === "string" || typeof item === "number") return item;
  if (typeof item !== "object") return String(item);
  const label = compactText(item.label ?? item.title ?? item.name ?? "", 80);
  const value = compactText(
    item.value ?? item.normalized_value ?? item.text ?? "",
    240,
  );
  if (label && value) return `${label}: ${value}`;
  return label || value || "Por confirmar";
}
