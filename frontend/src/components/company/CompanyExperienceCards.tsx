"use client";

import {
  ArrowRight,
  Armchair,
  BriefcaseBusiness,
  Building2,
  ChevronDown,
  ChevronUp,
  Columns,
  GraduationCap,
  HeartPulse,
  House,
  Landmark,
  Map as MapIcon,
  Route,
  Star,
  Trees,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { CompanyProfile } from "./company-types";
import styles from "./CompanyExperienceCards.module.css";

type ExperienceProject = {
  name?: string;
  typology?: string;
  normalized_typology?: string;
  original_typology?: string;
  location?: string;
  skills_demonstrated?: string[];
  source?: string;
};

type ExperienceSummary = {
  typology?: string;
  project_count?: number;
  experience_level?: string;
  experience_level_score?: number;
  origins?: string[];
  confidence?: number;
  projects?: ExperienceProject[];
};

type ExperienceSource = Partial<CompanyProfile> & {
  project_experience_summary?: ExperienceSummary[];
  project_experience_counts?: Record<string, number>;
  project_counts_by_typology?: Record<string, number>;
};

type TypologyCard = {
  typology: string;
  label: string;
  count: number;
  level: string;
  levelLabel: string;
  stars: number;
  confidence: number;
  origins: string[];
  accent: string;
  surface: string;
  icon: LucideIcon;
  projects: Array<{
    name: string;
    location: string;
    source?: string;
  }>;
};

type TypologyVisuals = {
  label: string;
  icon: LucideIcon;
  iconBackground: string;
  iconColor: string;
};

const TYPOLOGY_VISUALS: Record<string, TypologyVisuals> = {
  Educacao: {
    label: "Educação",
    icon: GraduationCap,
    iconBackground: "#E5F4EA",
    iconColor: "#347857",
  },
  Habitacao: {
    label: "Habitação",
    icon: House,
    iconBackground: "#E7F0F8",
    iconColor: "#3F6E96",
  },
  Cultura: {
    label: "Cultura",
    icon: Landmark,
    iconBackground: "#F8E8EF",
    iconColor: "#9A5F77",
  },
  Patrimonio: {
    label: "Património",
    icon: Columns,
    iconBackground: "#F4EDDB",
    iconColor: "#8A7441",
  },
  Reabilitacao: {
    label: "Reabilitação",
    icon: Building2,
    iconBackground: "#ECE8F6",
    iconColor: "#6F6097",
  },
  Saude: {
    label: "Saúde",
    icon: HeartPulse,
    iconBackground: "#F8E7E5",
    iconColor: "#A75E58",
  },
  Mobiliario: {
    label: "Mobiliário",
    icon: Armchair,
    iconBackground: "#F4ECE2",
    iconColor: "#8E6844",
  },
  Urbanismo: {
    label: "Urbanismo",
    icon: MapIcon,
    iconBackground: "#EDE9F7",
    iconColor: "#6F6192",
  },
  Paisagismo: {
    label: "Paisagismo",
    icon: Trees,
    iconBackground: "#E5F3E8",
    iconColor: "#4F805C",
  },
  Mobilidade: {
    label: "Mobilidade",
    icon: Route,
    iconBackground: "#FAEBDC",
    iconColor: "#9A7045",
  },
};

const DEFAULT_VISUALS: TypologyVisuals = {
  label: "Por confirmar",
  icon: BriefcaseBusiness,
  iconBackground: "#EDF1EF",
  iconColor: "#607269",
};

const TYPOLOGY_ALIASES: Array<[string, string[]]> = [
  ["Educacao", ["educacao", "educação", "escola", "escolar", "centro escolar", "ensino", "agrupamento", "school", "education"]],
  ["Saude", ["saude", "saúde", "hospital", "clínica", "clinic", "health", "centro de saude", "centro de saúde"]],
  ["Habitacao", ["habitacao", "habitação", "housing", "residential", "moradia", "apartamento", "dwelling"]],
  ["Patrimonio", ["patrimonio", "património", "heritage", "monumento", "historic"]],
  ["Reabilitacao", ["reabilitacao", "reabilitação", "requalificacao", "requalificação", "rehabilitation", "refurbishment"]],
  ["Mercados", ["mercado", "market", "municipal market"]],
  ["Mobiliario", ["mobiliario", "mobiliário", "furniture", "chair", "cadeira"]],
  ["Escritorios", ["escritorio", "escritório", "office", "office building", "workplace"]],
  ["Industria", ["industria", "indústria", "industrial", "factory", "warehousing"]],
  ["Paisagismo", ["paisagismo", "landscape", "garden", "jardim"]],
  ["Urbanismo", ["urbanismo", "urban planning", "planeamento urbano", "urban design"]],
  ["Comercio", ["comercio", "comércio", "retail", "shop", "store"]],
  ["Turismo", ["turismo", "hotel", "hospitality", "lodging"]],
  ["Cultura", ["cultura", "museum", "theatre", "biblioteca", "auditorio", "auditório"]],
  ["Desporto", ["desporto", "sport", "stadium", "pavilhao", "pavilhão"]],
  ["Infraestruturas", ["infraestrutura", "infraestruturas", "infrastructure", "roads", "utilities"]],
  ["Mobilidade", ["mobilidade", "mobility", "transport", "mobility infrastructure"]],
];

const NOISE_PATTERNS = [
  /back to top/i,
  /\bnews\b/i,
  /\bprofile\b/i,
  /\bpublications\b/i,
  /\bpublication\b/i,
  /\bhome\b/i,
  /\bmenu\b/i,
  /\bcontact\b/i,
  /\bsearch\b/i,
];

function cleanText(value: unknown): string {
  return String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeText(value: unknown): string {
  return cleanText(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function normalizeTypology(value: unknown): string {
  const text = normalizeText(value);
  if (!text) return "";

  for (const [canonical, aliases] of TYPOLOGY_ALIASES) {
    if (text === normalizeText(canonical)) return canonical;
    for (const alias of aliases) {
      const normalizedAlias = normalizeText(alias);
      if (
        text === normalizedAlias ||
        text.includes(normalizedAlias) ||
        normalizedAlias.includes(text)
      ) {
        return canonical;
      }
    }
  }

  return cleanText(value);
}

function displayTypology(value: string): string {
  return TYPOLOGY_VISUALS[value]?.label || cleanText(value) || "Por confirmar";
}

function resolveVisuals(typology: string): TypologyVisuals {
  return TYPOLOGY_VISUALS[typology] || {
    ...DEFAULT_VISUALS,
    label: cleanText(typology) || "Por confirmar",
  };
}

function experienceLabel(count: number, level?: string): string {
  const normalizedLevel = normalizeText(level);
  if (normalizedLevel.includes("especialista")) return "Experiência muito forte";
  if (normalizedLevel.includes("forte")) return "Experiência forte";
  if (normalizedLevel.includes("consistente")) return "Experiência moderada";
  if (normalizedLevel.includes("pontual")) return "Experiência inicial";

  if (count >= 11) return "Experiência muito forte";
  if (count >= 6) return "Experiência forte";
  if (count >= 3) return "Experiência moderada";
  if (count >= 1) return "Experiência inicial";
  return "Contagem por confirmar";
}

function starsForCount(count: number, level?: string): number {
  const normalizedLevel = normalizeText(level);
  if (normalizedLevel.includes("especialista")) return 5;
  if (normalizedLevel.includes("forte")) return 4;
  if (normalizedLevel.includes("consistente")) return 3;
  if (normalizedLevel.includes("pontual")) return 2;

  if (count >= 11) return 5;
  if (count >= 6) return 4;
  if (count >= 3) return 3;
  if (count >= 1) return 1;
  return 0;
}

function starRow(stars: number) {
  return Array.from({ length: 5 }, (_, index) => (
    <Star
      key={index}
      size={15}
      aria-hidden="true"
      className={index < stars ? styles.starFilled : styles.starEmpty}
      fill={index < stars ? "currentColor" : "none"}
    />
  ));
}

function isUsefulProject(project: ExperienceProject): boolean {
  const text = normalizeText([project.name, project.location].filter(Boolean).join(" "));
  if (!text) return false;
  return !NOISE_PATTERNS.some((pattern) => pattern.test(text));
}

function projectKey(project: { name?: string; location?: string }): string {
  return `${normalizeText(project.name)}|${normalizeText(project.location)}`;
}

function appendProject(
  card: TypologyCard,
  project: { name?: string; location?: string; source?: string },
) {
  const key = projectKey(project);
  if (!key || card.projects.some((item) => projectKey(item) === key)) {
    return;
  }

  card.projects.push({
    name: cleanText(project?.name) || "Projeto sem nome",
    location: cleanText(project?.location),
    source: project?.source,
  });
}

function collectProjects(profile: ExperienceSource): TypologyCard[] {
  const summary = Array.isArray(profile.project_experience_summary)
    ? profile.project_experience_summary
    : [];
  const countsByTypology =
    profile.project_counts_by_typology ||
    profile.project_experience_counts ||
    {};

  const cards = new Map<string, TypologyCard>();
  const summaryCounts = new Map<string, number>();
  const seenProjects = new Set<string>();
  const derivedCounts = new Map<string, number>();

  for (const item of summary) {
    const typologyKey = normalizeTypology(item?.typology);
    if (!typologyKey) continue;

    const visuals = resolveVisuals(typologyKey);
    const existing = cards.get(typologyKey) ?? {
      typology: typologyKey,
      label: displayTypology(typologyKey),
      count: 0,
      level: "",
      levelLabel: "",
      stars: 1,
      confidence: 0,
      origins: [],
      accent: visuals.iconColor,
      surface: visuals.iconBackground,
      icon: visuals.icon,
      projects: [],
    };

    const count = Number(item?.project_count ?? 0);
    if (Number.isFinite(count) && count > 0) {
      summaryCounts.set(
        typologyKey,
        Math.max(summaryCounts.get(typologyKey) || 0, count),
      );
    }
    existing.level = cleanText(item?.experience_level);
    existing.levelLabel = experienceLabel(existing.count, existing.level);
    existing.stars = starsForCount(existing.count, existing.level);
    existing.confidence = Number(item?.confidence ?? existing.confidence ?? 0);
    existing.origins = Array.from(
      new Set([...(existing.origins || []), ...((item?.origins as string[]) || [])]),
    ).filter(Boolean);

    for (const project of ((item?.projects || []) as ExperienceProject[]).filter(Boolean)) {
      if (isUsefulProject(project)) {
        appendProject(existing, project);
      }
    }

    cards.set(typologyKey, existing);
  }

  for (const [typology, countValue] of Object.entries(countsByTypology)) {
    const typologyKey = normalizeTypology(typology);
    if (!typologyKey) continue;

    const visuals = resolveVisuals(typologyKey);
    const count = Number(countValue ?? 0);
    const existing = cards.get(typologyKey) ?? {
      typology: typologyKey,
      label: displayTypology(typologyKey),
      count: 0,
      level: "",
      levelLabel: "",
      stars: 1,
      confidence: 0,
      origins: [],
      accent: visuals.iconColor,
      surface: visuals.iconBackground,
      icon: visuals.icon,
      projects: [],
    };

    if (Number.isFinite(count) && count > 0) {
      existing.count = Math.max(existing.count, count);
    }
    existing.levelLabel = experienceLabel(existing.count, existing.level);
    existing.stars = starsForCount(existing.count, existing.level);
    if (!existing.origins.includes("company_context")) {
      existing.origins.push("company_context");
    }
    cards.set(typologyKey, existing);
  }

  const projects = Array.isArray(profile.project_experience)
    ? profile.project_experience
    : [];

  for (const project of projects) {
    const typologyKey = normalizeTypology(
      project?.normalized_typology ||
        project?.typology ||
        project?.original_typology,
    );
    if (!typologyKey) continue;

    const visuals = resolveVisuals(typologyKey);
    const existing = cards.get(typologyKey) ?? {
      typology: typologyKey,
      label: displayTypology(typologyKey),
      count: 0,
      level: "",
      levelLabel: "",
      stars: 1,
      confidence: 0,
      origins: [],
      accent: visuals.iconColor,
      surface: visuals.iconBackground,
      icon: visuals.icon,
      projects: [],
    };

    if (isUsefulProject(project)) {
      const projectFingerprint = [
        normalizeText(project?.name),
        normalizeText(project?.location),
        typologyKey,
      ].join("|");
      if (!seenProjects.has(projectFingerprint)) {
        seenProjects.add(projectFingerprint);
        derivedCounts.set(typologyKey, (derivedCounts.get(typologyKey) || 0) + 1);
        appendProject(existing, project);
      }
    }

    existing.levelLabel = experienceLabel(existing.count, existing.level);
    existing.stars = starsForCount(existing.count, existing.level);
    if (!existing.origins.includes("company_profile")) {
      existing.origins.push("company_profile");
    }
    cards.set(typologyKey, existing);
  }

  for (const [typologyKey, derivedCount] of derivedCounts.entries()) {
    const card = cards.get(typologyKey);
    if (!card) continue;
    if (derivedCount > card.count) {
      card.count = derivedCount;
    }
    card.origins = Array.from(new Set([...card.origins, "company_profile"]));
    card.levelLabel = experienceLabel(card.count, card.level);
    card.stars = starsForCount(card.count, card.level);
  }

  for (const [typologyKey, summaryCount] of summaryCounts.entries()) {
    const card = cards.get(typologyKey);
    if (!card) continue;
    if (card.count <= 0) {
      card.count = summaryCount;
    }
    card.levelLabel = experienceLabel(card.count, card.level);
    card.stars = starsForCount(card.count, card.level);
  }

  for (const card of cards.values()) {
    card.count = Math.max(card.count, card.projects.length);
    card.levelLabel = experienceLabel(card.count, card.level);
    card.stars = starsForCount(card.count, card.level);
  }

  return Array.from(cards.values())
    .filter((card) => card.count > 0)
    .sort((a, b) => b.count - a.count || b.stars - a.stars || a.label.localeCompare(b.label, "pt"));
}

function ExperienceCard({
  card,
  forceOpen,
}: {
  card: TypologyCard;
  forceOpen?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const activeOpen = Boolean(forceOpen) || open;
  const hasProjects = card.projects.length > 0;
  const Icon = card.icon;

  return (
    <article className={styles.card}>
      <div
        className={styles.iconContainer}
        style={{
          ["--icon-bg" as string]: card.surface,
          ["--icon-color" as string]: card.accent,
        }}
      >
        <Icon size={20} strokeWidth={2} />
      </div>

      <h3 className={styles.typology}>{card.label}</h3>
      <p className={styles.projectCount}>
        {card.count} projeto{card.count === 1 ? "" : "s"}
      </p>

      <div
        className={styles.stars}
        role="img"
        aria-label={`${card.stars} de 5 estrelas`}
      >
        {starRow(card.stars)}
      </div>

      <p className={styles.experienceLevel}>{card.levelLabel}</p>

      <div className={styles.progressBar} aria-hidden="true">
        <span
          className={styles.progressFill}
          style={{ width: `${Math.max(20, card.stars * 20)}%` }}
        />
      </div>

      <div className={styles.spacer} />

      <button
        type="button"
        className={styles.viewProjectsAction}
        onClick={() => {
          if (!forceOpen) {
            setOpen((current) => !current);
          }
        }}
        aria-expanded={activeOpen}
      >
        {activeOpen ? "Ocultar projetos" : "Ver projetos"}
        {activeOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {activeOpen && (
        <div className={styles.projects}>
          {hasProjects ? (
            <ul className={styles.projectsList}>
              {card.projects.slice(0, 8).map((project, index) => (
                <li key={`${card.typology}-${index}`} className={styles.projectItem}>
                  <span className={styles.projectName}>{project.name}</span>
                  {project.location ? (
                    <span className={styles.projectMeta}>{project.location}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.projectsEmpty}>
              Projetos individuais ainda não disponíveis.
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function LegendItem({
  stars,
  label,
}: {
  stars: number;
  label: string;
}) {
  return (
    <div className={styles.legendItem}>
      <span className={styles.legendStars}>{starRow(stars)}</span>
      <span className={styles.legendLabel}>{label}</span>
    </div>
  );
}

export default function CompanyExperienceCards({
  profile,
}: {
  profile: ExperienceSource;
}) {
  const cards = useMemo(() => collectProjects(profile), [profile]);
  const [showAllProjects, setShowAllProjects] = useState(false);

  return (
    <section className={styles.container}>
      <div className={styles.headerRow}>
        <div className={styles.titleBlock}>
          <h2>Experiência por tipologia</h2>
          <p>
            Experiência consolidada a partir dos projetos identificados no perfil
            da empresa.
          </p>
        </div>

        <button
          type="button"
          className={styles.actionButton}
          onClick={() => setShowAllProjects((current) => !current)}
        >
          {showAllProjects ? "Ocultar projetos" : "Ver todos os projetos"}
          <ArrowRight size={14} />
        </button>
      </div>

      {cards.length === 0 ? (
        <div className={styles.emptyState}>
          <h3 className={styles.emptyTitle}>
            A experiência ainda não foi categorizada
          </h3>
          <p className={styles.emptyDescription}>
            Adicione ou valide projetos no perfil da empresa para criar o resumo
            por tipologia.
          </p>
        </div>
      ) : (
        <>
          <div className={styles.grid}>
            {cards.map((card) => (
              <ExperienceCard
                key={card.typology}
                card={card}
                forceOpen={showAllProjects}
              />
            ))}
          </div>

          <div className={styles.infoPanel}>
            <div className={styles.infoCopy}>
              <h3>Como funciona a experiência por tipologia?</h3>
              <p>
                A experiência é calculada com base nos projetos categorizados no
                perfil da empresa. Uma maior quantidade de projetos relevantes
                aumenta o nível de experiência e contribui para o matching com os
                concursos.
              </p>
            </div>

            <div className={styles.legend}>
              <LegendItem stars={1} label="Experiência inicial" />
              <LegendItem stars={3} label="Experiência moderada" />
              <LegendItem stars={4} label="Experiência forte" />
              <LegendItem stars={5} label="Experiência muito forte" />
            </div>
          </div>
        </>
      )}
    </section>
  );
}