"use client";

import {
  Accessibility,
  Boxes,
  Building2,
  CalendarClock,
  Droplets,
  FileWarning,
  Leaf,
  Map,
  Mountain,
  Network,
  Route,
  Sparkles,
  Users,
} from "lucide-react";

type Props = {
  program?: any;
};

type Theme = {
  label?: string;
  items?: string[];
  confirmed?: boolean;
  source_documents?: string[];
};

const ORDER = [
  "program_intervention",
  "landscape_public_space",
  "terrain_modeling",
  "mobility_access",
  "green_system",
  "drainage",
  "infrastructure_specialties",
  "bim_requirements",
  "technical_team",
  "phases_deadlines",
] as const;

const ICONS: Record<string, any> = {
  program_intervention: Map,
  landscape_public_space: Leaf,
  terrain_modeling: Mountain,
  mobility_access: Route,
  green_system: Leaf,
  drainage: Droplets,
  infrastructure_specialties: Network,
  bim_requirements: Boxes,
  technical_team: Users,
  phases_deadlines: CalendarClock,
};

function clean(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function unique(items: unknown, limit = 5): string[] {
  if (!Array.isArray(items)) return [];
  return Array.from(
    new Set(items.map(clean).filter(Boolean)),
  ).slice(0, limit);
}

export default function InterventionProgramSummaryCard({
  program,
}: Props) {
  const themes = (program?.themes || {}) as Record<string, Theme>;
  const inconsistencies = unique(program?.inconsistencies, 8);
  const sources = unique(program?.source_documents, 12);
  const area = clean(program?.area_intervencao?.value);
  const summary = clean(program?.summary) || "Informação ainda por confirmar nas peças.";
  const interventionType =
    clean(program?.intervention_type) ||
    "Arquitetura paisagista e espaço público";

  return (
    <article className="ip-card">
      <div className="ip-header">
        <div>
          <span className="ip-kicker">
            <Sparkles size={14} />
            Programa de intervenção
          </span>
          <h3>Síntese territorial e técnica</h3>
          <p>{summary}</p>
        </div>

        <div className="ip-badges">
          <span><Building2 size={15} />{interventionType}</span>
          {area ? <span><Accessibility size={15} />{area}</span> : null}
        </div>
      </div>

      <div className="ip-grid">
        {ORDER.map((key) => {
          const theme = themes[key] || {};
          const Icon = ICONS[key] || Map;
          const items = unique(theme.items, 4);

          return (
            <section
              key={key}
              className={items.length ? "ip-theme" : "ip-theme pending"}
            >
              <div className="ip-theme-title">
                <Icon size={17} />
                <h4>{clean(theme.label) || key}</h4>
              </div>
              {items.length ? (
                <ul>
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p>Informação ainda não confirmada nas peças.</p>
              )}
            </section>
          );
        })}
      </div>

      <div className="ip-audit-grid">
        <section className="ip-audit">
          <div className="ip-theme-title">
            <FileWarning size={17} />
            <h4>Inconsistências documentais</h4>
          </div>
          {inconsistencies.length ? (
            <ul>
              {inconsistencies.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p>Não foram registadas inconsistências documentais relevantes.</p>
          )}
        </section>

        <section className="ip-audit">
          <div className="ip-theme-title">
            <Network size={17} />
            <h4>Fontes</h4>
          </div>
          {sources.length ? (
            <ul>
              {sources.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p>As fontes serão listadas após a leitura das peças.</p>
          )}
        </section>
      </div>

      <style jsx>{`
        .ip-card {
          padding: 22px;
          border: 1px solid #dfe2d6;
          border-radius: 18px;
          background: #fff;
        }

        .ip-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 22px;
        }

        .ip-kicker {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: #6e7c47;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }

        .ip-header h3 {
          margin: 8px 0;
          font-size: 22px;
          line-height: 1.1;
        }

        .ip-header p {
          max-width: 900px;
          margin: 0;
          color: #4b5146;
          font-size: 14px;
          line-height: 1.58;
        }

        .ip-badges {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 8px;
        }

        .ip-badges span {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 9px 13px;
          border: 1px solid #dce2cf;
          border-radius: 999px;
          background: #f3f6eb;
          color: #4f5f2d;
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
        }

        .ip-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
          margin-top: 18px;
        }

        .ip-theme,
        .ip-audit {
          min-height: 160px;
          padding: 15px;
          border: 1px solid #e4e6dc;
          border-radius: 14px;
          background: #fff;
        }

        .ip-theme.pending {
          background: #fbfaf5;
        }

        .ip-theme-title {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #536936;
        }

        .ip-theme-title h4 {
          margin: 0;
          color: #20241e;
          font-size: 14px;
        }

        .ip-theme ul,
        .ip-audit ul {
          margin: 12px 0 0;
          padding-left: 18px;
          color: #3c4038;
          font-size: 13px;
          line-height: 1.55;
        }

        .ip-theme li + li,
        .ip-audit li + li {
          margin-top: 7px;
        }

        .ip-theme p,
        .ip-audit p {
          margin: 12px 0 0;
          color: #7b7f76;
          font-size: 13px;
          line-height: 1.5;
        }

        .ip-audit-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
          margin-top: 10px;
        }

        .ip-audit {
          min-height: 120px;
          background: #f8f9f4;
        }

        @media (max-width: 920px) {
          .ip-header {
            flex-direction: column;
          }

          .ip-badges {
            align-items: flex-start;
          }

          .ip-grid,
          .ip-audit-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </article>
  );
}
