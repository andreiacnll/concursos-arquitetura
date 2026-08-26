"use client";

import { useEffect, useState } from "react";
import { ArrowRight, X } from "lucide-react";

type Section = {
  title: string;
  items: Array<{ label: string; value: string }>;
};

export function DomainDetailsButton({
  label,
  title,
  sections,
}: {
  label: string;
  title: string;
  sections: Section[];
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        className="dc-domain-open"
        onClick={() => setOpen(true)}
      >
        {label}
        <ArrowRight size={15} />
      </button>

      {open ? (
        <div
          className="dc-domain-modal"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) setOpen(false);
          }}
        >
          <section
            className="dc-domain-panel"
            role="dialog"
            aria-modal="true"
            aria-label={title}
          >
            <header>
              <div>
                <span>Informação documental completa</span>
                <h2>{title}</h2>
              </div>
              <button
                type="button"
                aria-label="Fechar"
                onClick={() => setOpen(false)}
              >
                <X size={18} />
              </button>
            </header>

            <div className="dc-domain-body">
              {sections.map((section) => (
                <article key={section.title}>
                  <h3>{section.title}</h3>
                  {section.items.map((item) => (
                    <div
                      className="dc-domain-row"
                      key={`${section.title}-${item.label}-${item.value}`}
                    >
                      <span>{item.label}</span>
                      <strong>{item.value || "Por confirmar"}</strong>
                    </div>
                  ))}
                </article>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      <style jsx>{`
        .dc-domain-open {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          width: 100%;
          margin-top: 12px;
          padding: 12px 8px 2px;
          border: 0;
          border-top: 1px solid #e8e9e3;
          background: transparent;
          color: #5f763d;
          font-size: 11px;
          font-weight: 800;
          cursor: pointer;
        }

        .dc-domain-modal {
          position: fixed;
          inset: 0;
          z-index: 1300;
          display: grid;
          place-items: center;
          padding: 24px;
          background: rgba(24, 27, 21, 0.5);
          backdrop-filter: blur(4px);
        }

        .dc-domain-panel {
          width: min(960px, 100%);
          max-height: calc(100vh - 48px);
          overflow: hidden;
          border: 1px solid #dfe1d9;
          border-radius: 18px;
          background: #fff;
          box-shadow: 0 28px 80px rgba(20, 23, 18, 0.22);
        }

        .dc-domain-panel > header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
          padding: 22px 24px 18px;
          border-bottom: 1px solid #e7e8e2;
        }

        .dc-domain-panel > header span {
          color: #6d8044;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.13em;
          text-transform: uppercase;
        }

        .dc-domain-panel > header h2 {
          margin: 5px 0 0;
          font-size: 25px;
        }

        .dc-domain-panel > header button {
          display: grid;
          width: 38px;
          height: 38px;
          place-items: center;
          border: 1px solid #dfe1d9;
          border-radius: 999px;
          background: #fff;
          cursor: pointer;
        }

        .dc-domain-body {
          max-height: calc(100vh - 160px);
          overflow-y: auto;
          padding: 20px 24px 28px;
        }

        .dc-domain-body article + article {
          margin-top: 24px;
        }

        .dc-domain-body h3 {
          margin: 0 0 10px;
          font-size: 15px;
        }

        .dc-domain-row {
          display: grid;
          grid-template-columns: 210px minmax(0, 1fr);
          gap: 22px;
          padding: 13px 0;
          border-bottom: 1px solid #ecece7;
        }

        .dc-domain-row span {
          color: #666c63;
          font-size: 12px;
        }

        .dc-domain-row strong {
          font-size: 13px;
          line-height: 1.55;
        }
      `}</style>
    </>
  );
}
