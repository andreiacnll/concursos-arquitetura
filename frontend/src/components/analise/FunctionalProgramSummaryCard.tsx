"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Layers3, Sparkles } from "lucide-react";
import {
  buildFunctionalProgramViewModel,
  compactText,
  EMPTY,
} from "@/components/analise/functionalProgramModel";
import FunctionalProgramModal from "@/components/analise/FunctionalProgramModal";

type Props = {
  functionalProgram?: any;
  extraction?: any;
};

export default function FunctionalProgramSummaryCard({
  functionalProgram,
  extraction,
}: Props) {
  const [open, setOpen] = useState(false);

  const viewModel = useMemo(
    () =>
      buildFunctionalProgramViewModel({
        functionalProgram,
        extraction,
      }),
    [functionalProgram, extraction],
  );

  return (
    <article className="fp-card">
      <div className="fp-header">
        <div className="fp-title">
          <span className="fp-kicker">
            <Sparkles size={14} />
            Programa funcional
          </span>
          <h3>Resumo do programa preliminar</h3>
          <p>{compactText(viewModel.summary, 760) || EMPTY}</p>
        </div>

        <div className="fp-badge">
          <Layers3 size={16} />
          {compactText(viewModel.interventionType, 60) || EMPTY}
        </div>
      </div>

      <div className="fp-metrics">
        {viewModel.metrics.map((metric) => (
          <div
            key={metric.label}
            className={metric.confirmed ? "fp-metric" : "fp-metric pending"}
          >
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
      </div>

      <div className="fp-preview-grid">
        {viewModel.previewSections.map((section) => (
          <section key={section.key} className="fp-preview-card">
            <h4>{section.title}</h4>
            {section.items.length ? (
              <ul>
                {section.items.map((item: string) => (
                  <li key={item}>{compactText(item, 110)}</li>
                ))}
              </ul>
            ) : (
              <p>{section.empty}</p>
            )}
          </section>
        ))}
      </div>

      <button
        type="button"
        className="fp-open"
        onClick={() => setOpen(true)}
      >
        Ver programa funcional completo
        <ArrowRight size={16} />
      </button>

      <FunctionalProgramModal
        open={open}
        title="Programa funcional completo"
        summary={viewModel.summary}
        interventionType={viewModel.interventionType}
        sections={viewModel.modalSections}
        activeSection={null}
        onClose={() => setOpen(false)}
      />

      <style jsx>{`
        .fp-card {
          padding: 22px;
          border: 1px solid #dfe2d6;
          border-radius: 18px;
          background: #fff;
        }

        .fp-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 18px;
        }

        .fp-kicker {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: #6e7c47;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .fp-title h3 {
          margin: 8px 0;
          font-size: 22px;
          line-height: 1.1;
        }

        .fp-title p {
          max-width: 900px;
          margin: 0;
          color: #4b5146;
          font-size: 14px;
          line-height: 1.55;
        }

        .fp-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          border: 1px solid #dce2cf;
          border-radius: 999px;
          background: #f3f6eb;
          color: #4f5f2d;
          font-size: 13px;
          font-weight: 700;
          white-space: nowrap;
        }

        .fp-metrics,
        .fp-preview-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 10px;
          margin-top: 14px;
        }

        .fp-metric,
        .fp-preview-card {
          padding: 14px;
          border: 1px solid #e4e6dc;
          border-radius: 14px;
          background: #fff;
        }

        .fp-metric {
          min-height: 88px;
        }

        .fp-metric.pending {
          background: #fbfaf5;
        }

        .fp-metric span {
          display: block;
          margin-bottom: 8px;
          color: #6d7268;
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .fp-metric strong {
          display: block;
          color: #20241e;
          font-size: 16px;
          line-height: 1.3;
        }

        .fp-preview-card {
          min-height: 168px;
        }

        .fp-preview-card h4 {
          margin: 0 0 10px;
          font-size: 14px;
        }

        .fp-preview-card ul {
          margin: 0;
          padding-left: 18px;
          color: #3c4038;
          font-size: 13px;
          line-height: 1.55;
        }

        .fp-preview-card li + li {
          margin-top: 6px;
        }

        .fp-preview-card p {
          margin: 0;
          color: #7b7f76;
          font-size: 13px;
        }

        .fp-open {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 9px;
          width: 100%;
          margin-top: 16px;
          padding: 13px 16px;
          border: 1px solid #dce2cf;
          border-radius: 11px;
          background: #f5f7ef;
          color: #536936;
          font-size: 13px;
          font-weight: 800;
          cursor: pointer;
        }

        @media (max-width: 1200px) {
          .fp-metrics,
          .fp-preview-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 720px) {
          .fp-header {
            flex-direction: column;
          }

          .fp-metrics,
          .fp-preview-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </article>
  );
}
