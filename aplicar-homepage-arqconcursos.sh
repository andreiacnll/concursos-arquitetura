#!/usr/bin/env bash
set -euo pipefail

# Executar a partir da raiz do projeto:
#   bash aplicar-homepage.sh
#
# Estrutura esperada:
#   concursos-arquitetura/
#   └── frontend/src/app/

ROOT_DIR="$(pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
APP_DIR="$FRONTEND_DIR/src/app"
COMPONENTS_DIR="$FRONTEND_DIR/src/components"
PUBLIC_DIR="$FRONTEND_DIR/public"
BACKUP_DIR="$FRONTEND_DIR/.backup-homepage-$(date +%Y%m%d-%H%M%S)"

if [ ! -d "$APP_DIR" ]; then
  echo "ERRO: não encontrei $APP_DIR"
  echo "Executa este script na raiz do projeto concursos-arquitetura."
  exit 1
fi

echo "→ A criar backup em $BACKUP_DIR"
mkdir -p "$BACKUP_DIR/app" "$BACKUP_DIR/components"

for file in page.tsx layout.tsx globals.css; do
  if [ -f "$APP_DIR/$file" ]; then
    cp "$APP_DIR/$file" "$BACKUP_DIR/app/$file"
  fi
done

if [ -d "$COMPONENTS_DIR" ]; then
  cp -R "$COMPONENTS_DIR/." "$BACKUP_DIR/components/" 2>/dev/null || true
fi

mkdir -p "$COMPONENTS_DIR" "$PUBLIC_DIR"

echo "→ A instalar lucide-react"
cd "$FRONTEND_DIR"
npm install lucide-react

echo "→ A criar ilustração arquitetónica"
cat > "$PUBLIC_DIR/hero-architecture.svg" <<'SVG'
<svg width="1400" height="850" viewBox="0 0 1400 850" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sky" x1="700" y1="0" x2="700" y2="850" gradientUnits="userSpaceOnUse">
      <stop stop-color="#F1F2F1"/>
      <stop offset="1" stop-color="#D9D6CE"/>
    </linearGradient>
    <linearGradient id="wall" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#F4F1EB"/>
      <stop offset="1" stop-color="#C8C3B9"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="160%">
      <feDropShadow dx="0" dy="22" stdDeviation="20" flood-color="#544F45" flood-opacity=".16"/>
    </filter>
  </defs>
  <rect width="1400" height="850" fill="url(#sky)"/>
  <path d="M0 640C186 610 331 623 493 652C708 691 916 688 1400 612V850H0V640Z" fill="#CFC8BA"/>
  <path d="M0 675C271 647 439 691 635 702C862 715 1097 665 1400 652V850H0V675Z" fill="#E5E0D7"/>
  <g filter="url(#shadow)">
    <path d="M176 586V344L555 225V585L176 586Z" fill="url(#wall)"/>
    <path d="M555 225L775 283V585H555V225Z" fill="#D2CEC5"/>
    <path d="M555 345H843V585H555V345Z" fill="#ECE8E0"/>
    <path d="M716 347H843V585H716V347Z" fill="#B9B6B0"/>
    <path d="M747 379H842V584H747V379Z" fill="#252828"/>
    <path d="M842 325L1030 277V584H842V325Z" fill="url(#wall)"/>
    <path d="M1030 277L1114 333V584H1030V277Z" fill="#D8D4CC"/>
    <path d="M1059 462H1248V584H1059V462Z" fill="#E9E5DD"/>
    <path d="M1219 435L1309 466V584H1219V435Z" fill="#C9C5BC"/>
  </g>
  <path d="M479 585H1008L919 704H348L479 585Z" fill="#F5F2EC"/>
  <path d="M519 602H985M496 623H968M474 646H949M452 670H931" stroke="#C7C1B7" stroke-width="4"/>
  <g stroke="#A19D94" stroke-width="3">
    <path d="M1243 313V587"/>
    <path d="M1243 347C1192 333 1176 283 1199 247C1227 204 1290 217 1303 264C1313 302 1285 340 1243 347Z" fill="#7E8A69"/>
    <path d="M1243 328C1280 314 1328 330 1335 369C1341 405 1306 429 1271 415C1246 405 1237 367 1243 328Z" fill="#71805D"/>
    <path d="M1240 325C1205 314 1167 332 1164 368C1161 399 1191 421 1221 411C1244 403 1250 361 1240 325Z" fill="#8B9675"/>
  </g>
  <g opacity=".28" stroke="#8C877D">
    <path d="M176 395H555M176 456H555M176 518H555"/>
    <path d="M302 304V586M428 264V586"/>
    <path d="M842 383H1030M842 446H1030M842 510H1030"/>
  </g>
</svg>
SVG

echo "→ A criar layout.tsx"
cat > "$APP_DIR/layout.tsx" <<'TSX'
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ArqConcursos | Concursos públicos de arquitetura",
  description:
    "Encontra concursos públicos de arquitetura, urbanismo e paisagismo em Portugal.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
TSX

echo "→ A criar tipos"
cat > "$COMPONENTS_DIR/competition-types.ts" <<'TS'
export type Concurso = {
  id: number;
  titulo: string;
  entidade: string;
  link: string;
  data: string;
  relevante: number;
  data_limite: string | null;
  preco_base: string | null;
  estado: "aberto" | "encerrado" | "sem_prazo";
  distrito?: string | null;
  municipio?: string | null;
  categoria?: string | null;
  tipo_procedimento?: string | null;
};
TS

echo "→ A criar Navbar"
cat > "$COMPONENTS_DIR/Navbar.tsx" <<'TSX'
import Link from "next/link";
import { Sun } from "lucide-react";

function LogoMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 38 34"
      className="h-8 w-9"
      fill="none"
    >
      <path d="M4 29L15.5 4L25 29" stroke="currentColor" strokeWidth="2.2" />
      <path d="M27.5 18L33.5 29" stroke="currentColor" strokeWidth="2.2" />
    </svg>
  );
}

export default function Navbar() {
  return (
    <header className="site-header">
      <div className="site-container navbar">
        <Link href="/" className="brand" aria-label="ArqConcursos">
          <LogoMark />
          <span>ARQCONCURSOS</span>
        </Link>

        <nav className="desktop-nav" aria-label="Navegação principal">
          <Link href="#concursos">Concursos</Link>
          <Link href="#sobre">Sobre</Link>
          <Link href="#como-funciona">Como funciona</Link>
          <Link href="#newsletter">Newsletter</Link>
        </nav>

        <div className="navbar-actions">
          <button className="icon-button" type="button" aria-label="Alterar tema">
            <Sun size={18} strokeWidth={1.8} />
          </button>
          <button className="primary-button small" type="button">
            Entrar
          </button>
        </div>
      </div>
    </header>
  );
}
TSX

echo "→ A criar CompetitionCard"
cat > "$COMPONENTS_DIR/CompetitionCard.tsx" <<'TSX'
import {
  Bookmark,
  CalendarDays,
  ExternalLink,
  MapPin,
} from "lucide-react";
import type { Concurso } from "./competition-types";

const imageClasses = [
  "card-image image-school",
  "card-image image-housing",
  "card-image image-square",
  "card-image image-civic",
  "card-image image-cultural",
  "card-image image-landscape",
];

function formatDate(value: string | null) {
  if (!value) return "Sem prazo indicado";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("pt-PT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function getCategory(title: string) {
  const text = title.toLowerCase();

  if (text.includes("escola") || text.includes("educa")) return "Escolas";
  if (text.includes("habita") || text.includes("resid")) return "Habitação";
  if (text.includes("jardim") || text.includes("paisag")) return "Paisagismo";
  if (text.includes("praça") || text.includes("largo") || text.includes("rua"))
    return "Espaço público";
  if (text.includes("saúde") || text.includes("hospital")) return "Saúde";
  if (text.includes("patrim") || text.includes("museu")) return "Património";

  return "Arquitetura";
}

function getFreshness(dateValue: string) {
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return null;

  const now = new Date();
  const diff = Math.floor(
    (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diff <= 0) return "Hoje";
  if (diff === 1) return "Ontem";
  if (diff <= 7) return `${diff} dias`;
  return null;
}

export default function CompetitionCard({
  concurso,
  index,
}: {
  concurso: Concurso;
  index: number;
}) {
  const category = concurso.categoria || getCategory(concurso.titulo);
  const freshness = getFreshness(concurso.data);
  const location =
    concurso.municipio || concurso.distrito || concurso.entidade || "Portugal";

  return (
    <article className="competition-card">
      <div className={imageClasses[index % imageClasses.length]}>
        {freshness && <span className="freshness-badge">{freshness}</span>}
        <div className="architecture-shape" />
      </div>

      <div className="competition-card-body">
        <div className="card-heading-row">
          <div>
            <p className="category-label">{category}</p>
            <h3>{concurso.titulo}</h3>
          </div>

          <button type="button" className="bookmark-button" aria-label="Guardar">
            <Bookmark size={19} strokeWidth={1.65} />
          </button>
        </div>

        <div className="card-meta">
          <span>
            <MapPin size={15} />
            {location}
          </span>
          <span>
            <CalendarDays size={15} />
            {formatDate(concurso.data_limite)}
          </span>
        </div>

        <div className="card-footer">
          <span>{concurso.tipo_procedimento || "Concurso público"}</span>
          <strong>{concurso.preco_base || "Valor não indicado"}</strong>
        </div>

        <a
          className="card-link"
          href={concurso.link}
          target="_blank"
          rel="noreferrer"
          aria-label={`Abrir ${concurso.titulo}`}
        >
          <ExternalLink size={16} />
        </a>
      </div>
    </article>
  );
}
TSX

echo "→ A criar Dashboard"
cat > "$COMPONENTS_DIR/CompetitionsDashboard.tsx" <<'TSX'
"use client";

import { useMemo, useState } from "react";
import {
  Building2,
  CalendarDays,
  ChevronDown,
  Filter,
  Grid2X2,
  Landmark,
  List,
  MapPin,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import CompetitionCard from "./CompetitionCard";
import type { Concurso } from "./competition-types";

const categories = [
  "Todos",
  "Escolas",
  "Habitação",
  "Saúde",
  "Espaço público",
  "Património",
];

function categoryForTitle(title: string) {
  const text = title.toLowerCase();

  if (text.includes("escola") || text.includes("educa")) return "Escolas";
  if (text.includes("habita") || text.includes("resid")) return "Habitação";
  if (text.includes("saúde") || text.includes("hospital")) return "Saúde";
  if (
    text.includes("praça") ||
    text.includes("largo") ||
    text.includes("rua") ||
    text.includes("espaço público")
  )
    return "Espaço público";
  if (text.includes("patrim") || text.includes("museu")) return "Património";

  return "Outros";
}

function uniqueCount(values: Array<string | null | undefined>) {
  return new Set(values.filter(Boolean)).size;
}

export default function CompetitionsDashboard({
  concursos,
}: {
  concursos: Concurso[];
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Todos");
  const [district, setDistrict] = useState("Todos os distritos");
  const [sort, setSort] = useState("recentes");

  const districts = useMemo(
    () =>
      Array.from(
        new Set(
          concursos
            .map((item) => item.distrito)
            .filter((item): item is string => Boolean(item)),
        ),
      ).sort((a, b) => a.localeCompare(b, "pt")),
    [concursos],
  );

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    const items = concursos.filter((item) => {
      const haystack = [
        item.titulo,
        item.entidade,
        item.distrito,
        item.municipio,
        item.preco_base,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesQuery = !normalizedQuery || haystack.includes(normalizedQuery);
      const matchesCategory =
        category === "Todos" || categoryForTitle(item.titulo) === category;
      const matchesDistrict =
        district === "Todos os distritos" || item.distrito === district;

      return matchesQuery && matchesCategory && matchesDistrict;
    });

    return [...items].sort((a, b) => {
      const dateA = new Date(a.data).getTime() || 0;
      const dateB = new Date(b.data).getTime() || 0;
      return sort === "antigos" ? dateA - dateB : dateB - dateA;
    });
  }, [concursos, query, category, district, sort]);

  const now = new Date();
  const sevenDaysAgo = new Date(now);
  sevenDaysAgo.setDate(now.getDate() - 7);

  const newThisWeek = concursos.filter((item) => {
    const date = new Date(item.data);
    return !Number.isNaN(date.getTime()) && date >= sevenDaysAgo;
  }).length;

  const active = concursos.filter((item) => item.estado === "aberto").length;
  const municipalityCount =
    uniqueCount(concursos.map((item) => item.municipio)) ||
    uniqueCount(concursos.map((item) => item.distrito));
  const entityCount = uniqueCount(concursos.map((item) => item.entidade));

  return (
    <>
      <section className="hero-section">
        <div className="site-container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Concursos públicos de arquitetura</p>
            <h1>
              Encontra oportunidades.
              <br />
              Constrói o futuro.
            </h1>
            <p className="hero-description">
              Acompanha concursos públicos de arquitetura em Portugal de forma
              simples, rápida e organizada.
            </p>

            <div className="search-row">
              <label className="search-box">
                <Search size={20} strokeWidth={1.8} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Pesquisar concursos, entidades, locais..."
                />
              </label>
              <button className="search-button" type="button" aria-label="Pesquisar">
                <Search size={22} />
              </button>
            </div>

            <div className="category-pills">
              {categories.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setCategory(item)}
                  className={category === item ? "active" : ""}
                >
                  {item}
                </button>
              ))}
              <button type="button">
                Mais <ChevronDown size={15} />
              </button>
            </div>
          </div>

          <div className="hero-visual-wrap">
            <div className="hero-visual" />
          </div>

          <div className="stats-panel">
            <div className="stat">
              <Building2 />
              <div>
                <strong>{active || concursos.length}</strong>
                <span>Concursos ativos</span>
              </div>
            </div>
            <div className="stat">
              <CalendarDays />
              <div>
                <strong>{newThisWeek}</strong>
                <span>Novos esta semana</span>
              </div>
            </div>
            <div className="stat">
              <MapPin />
              <div>
                <strong>{municipalityCount}</strong>
                <span>Municípios</span>
              </div>
            </div>
            <div className="stat">
              <Landmark />
              <div>
                <strong>{entityCount}</strong>
                <span>Entidades públicas</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="concursos" className="listing-section">
        <div className="site-container listing-shell">
          <aside className="filters-panel">
            <div className="filters-title">
              <Filter size={17} />
              <span>Filtrar</span>
            </div>

            <div className="filter-group">
              <label htmlFor="district">Distrito</label>
              <select
                id="district"
                value={district}
                onChange={(event) => setDistrict(event.target.value)}
              >
                <option>Todos os distritos</option>
                {districts.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <p>Tipo de procedimento</p>
              {[
                "Concurso público",
                "Concurso limitado por prévia qualificação",
                "Concurso de conceção",
                "Consulta prévia",
              ].map((label, index) => (
                <label className="check-row" key={label}>
                  <input type="checkbox" defaultChecked={index === 0} />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="filter-group">
              <p>Tipo de serviço</p>
              {[
                "Elaboração de projeto",
                "Revisão / Análise de projeto",
                "Concurso de conceção",
                "Fiscalização / Coordenação",
              ].map((label) => (
                <label className="check-row" key={label}>
                  <input type="checkbox" />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="filter-group value-filter">
              <p>Valor estimado</p>
              <div className="range-track">
                <span />
              </div>
              <div className="range-labels">
                <span>€ 0</span>
                <span>€ 5M+</span>
              </div>
            </div>
          </aside>

          <div className="results-panel">
            <div className="results-toolbar">
              <p>
                <strong>{filtered.length}</strong> concursos encontrados
              </p>

              <div className="toolbar-actions">
                <span>Ordenar por</span>
                <select value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="recentes">Mais recentes</option>
                  <option value="antigos">Mais antigos</option>
                </select>
                <div className="view-toggle">
                  <button type="button" className="active" aria-label="Vista em grelha">
                    <Grid2X2 size={18} />
                  </button>
                  <button type="button" aria-label="Vista em lista">
                    <List size={19} />
                  </button>
                </div>
              </div>
            </div>

            {filtered.length > 0 ? (
              <div className="competition-grid">
                {filtered.map((concurso, index) => (
                  <CompetitionCard
                    key={concurso.id}
                    concurso={concurso}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <SlidersHorizontal size={28} />
                <h2>Não encontrámos concursos</h2>
                <p>Experimenta alterar a pesquisa ou os filtros selecionados.</p>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}
TSX

echo "→ A criar page.tsx"
cat > "$APP_DIR/page.tsx" <<'TSX'
import CompetitionsDashboard from "@/components/CompetitionsDashboard";
import Navbar from "@/components/Navbar";
import type { Concurso } from "@/components/competition-types";

async function getConcursos(): Promise<Concurso[]> {
  try {
    const response = await fetch(
      "http://127.0.0.1:8000/concursos?estado=todos&limite=100",
      { cache: "no-store" },
    );

    if (!response.ok) {
      throw new Error(`A API respondeu com o estado ${response.status}`);
    }

    const data = await response.json();

    if (Array.isArray(data)) return data;
    if (Array.isArray(data.resultados)) return data.resultados;

    return [];
  } catch (error) {
    console.error("Erro ao carregar concursos:", error);
    return [];
  }
}

export default async function Home() {
  const concursos = await getConcursos();

  return (
    <main>
      <Navbar />
      <CompetitionsDashboard concursos={concursos} />
    </main>
  );
}
TSX

echo "→ A criar globals.css"
cat > "$APP_DIR/globals.css" <<'CSS'
@import "tailwindcss";

:root {
  --background: #f7f7f5;
  --surface: #ffffff;
  --foreground: #181a1d;
  --muted: #6f7378;
  --line: #e5e5e1;
  --accent: #607b43;
  --accent-soft: #e8eee1;
  --shadow: 0 18px 50px rgba(24, 26, 29, 0.07);
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background:
    radial-gradient(circle at 12% 4%, rgba(255, 255, 255, 0.95), transparent 32rem),
    var(--background);
  color: var(--foreground);
  font-family: var(--font-geist-sans), Arial, Helvetica, sans-serif;
}

button,
input,
select {
  font: inherit;
}

button,
a,
select {
  -webkit-tap-highlight-color: transparent;
}

button,
a {
  transition:
    background-color 180ms ease,
    color 180ms ease,
    border-color 180ms ease,
    transform 180ms ease,
    box-shadow 180ms ease;
}

.site-container {
  width: min(1500px, calc(100% - 64px));
  margin-inline: auto;
}

.site-header {
  position: relative;
  z-index: 20;
  border-bottom: 1px solid rgba(229, 229, 225, 0.8);
  background: rgba(255, 255, 255, 0.83);
  backdrop-filter: blur(18px);
}

.navbar {
  min-height: 78px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 18px;
  width: fit-content;
  color: var(--foreground);
  text-decoration: none;
}

.brand span {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.24em;
}

.desktop-nav {
  display: flex;
  align-items: center;
  gap: 44px;
}

.desktop-nav a {
  color: #303235;
  text-decoration: none;
  font-size: 14px;
}

.desktop-nav a:hover {
  color: var(--accent);
}

.navbar-actions {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 18px;
}

.icon-button,
.primary-button,
.search-button {
  border: 0;
  cursor: pointer;
}

.icon-button {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: white;
}

.icon-button:hover {
  background: #f1f1ee;
  transform: translateY(-1px);
}

.primary-button {
  min-height: 42px;
  padding: 0 24px;
  border-radius: 7px;
  background: #1b1d20;
  color: white;
  font-weight: 600;
}

.primary-button:hover {
  background: #303235;
  transform: translateY(-1px);
}

.hero-section {
  padding: 28px 0 12px;
}

.hero-grid {
  position: relative;
  display: grid;
  grid-template-columns: 1.04fr 0.96fr;
  min-height: 580px;
  align-items: center;
  gap: 68px;
}

.hero-copy {
  padding-left: 4px;
  padding-bottom: 70px;
}

.eyebrow,
.category-label {
  margin: 0;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.11em;
  font-size: 12px;
  font-weight: 700;
}

.hero-copy h1 {
  max-width: 710px;
  margin: 18px 0 16px;
  font-size: clamp(48px, 5vw, 78px);
  line-height: 0.99;
  font-weight: 520;
  letter-spacing: -0.055em;
}

.hero-description {
  max-width: 570px;
  margin: 0;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.65;
}

.search-row {
  display: flex;
  align-items: stretch;
  gap: 10px;
  margin-top: 34px;
  max-width: 730px;
}

.search-box {
  min-height: 52px;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 18px;
  border: 1px solid #d9dad7;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: #999c9f;
  box-shadow: 0 10px 28px rgba(24, 26, 29, 0.035);
}

.search-box:focus-within {
  border-color: #a9af9f;
  box-shadow: 0 0 0 4px rgba(96, 123, 67, 0.08);
}

.search-box input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--foreground);
}

.search-box input::placeholder {
  color: #a1a3a5;
}

.search-button {
  width: 58px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #1b1d20;
  color: white;
  box-shadow: 0 12px 24px rgba(24, 26, 29, 0.16);
}

.search-button:hover {
  background: #303235;
  transform: translateY(-1px);
}

.category-pills {
  margin-top: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.category-pills button {
  min-height: 39px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 17px;
  border: 1px solid #dedfdb;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  color: #303235;
  cursor: pointer;
  font-size: 13px;
}

.category-pills button:hover,
.category-pills button.active {
  border-color: #1b1d20;
  background: #1b1d20;
  color: white;
  box-shadow: 0 8px 18px rgba(24, 26, 29, 0.13);
}

.hero-visual-wrap {
  align-self: stretch;
  display: flex;
  align-items: center;
  padding-bottom: 78px;
}

.hero-visual {
  width: 100%;
  height: 410px;
  border-radius: 9px;
  background-image: url("/hero-architecture.svg");
  background-size: cover;
  background-position: center;
  box-shadow: inset 0 0 0 1px rgba(24, 26, 29, 0.03);
}

.stats-panel {
  position: absolute;
  right: 34px;
  bottom: 12px;
  width: min(700px, 54%);
  min-height: 100px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  align-items: center;
  padding: 20px 16px;
  border: 1px solid rgba(229, 229, 225, 0.9);
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow);
  backdrop-filter: blur(16px);
}

.stat {
  min-height: 58px;
  display: flex;
  align-items: flex-start;
  gap: 13px;
  padding: 0 18px;
  border-left: 1px solid var(--line);
}

.stat:first-child {
  border-left: 0;
}

.stat svg {
  flex: none;
  margin-top: 2px;
  width: 23px;
  height: 23px;
  stroke-width: 1.8;
}

.stat div {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat strong {
  font-size: 21px;
  line-height: 1;
  font-weight: 540;
}

.stat span {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.listing-section {
  padding: 0 0 90px;
}

.listing-shell {
  display: grid;
  grid-template-columns: 300px 1fr;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.65);
  box-shadow: 0 18px 50px rgba(24, 26, 29, 0.035);
}

.filters-panel {
  padding: 30px 24px 36px;
  border-right: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.62);
}

.filters-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 30px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 12px;
  font-weight: 700;
}

.filter-group {
  padding: 0 0 28px;
}

.filter-group + .filter-group {
  border-top: 1px solid #efefec;
  padding-top: 25px;
}

.filter-group > label:first-child,
.filter-group > p {
  display: block;
  margin: 0 0 13px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #303235;
  font-size: 11px;
  font-weight: 700;
}

.filter-group select,
.results-toolbar select {
  width: 100%;
  min-height: 42px;
  border: 1px solid #dcdeda;
  border-radius: 7px;
  outline: 0;
  background: white;
  color: #55585b;
  padding: 0 38px 0 13px;
}

.check-row {
  display: flex !important;
  align-items: flex-start;
  gap: 10px;
  margin: 10px 0 !important;
  color: #303235 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  font-size: 13px !important;
  font-weight: 400 !important;
  line-height: 1.35;
  cursor: pointer;
}

.check-row input {
  width: 16px;
  height: 16px;
  margin: 1px 0 0;
  accent-color: #1b1d20;
}

.range-track {
  height: 4px;
  margin-top: 22px;
  border-radius: 999px;
  background: #e6e7e3;
}

.range-track span {
  display: block;
  width: 62%;
  height: 100%;
  border-radius: inherit;
  background: #1b1d20;
}

.range-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  color: var(--muted);
  font-size: 11px;
}

.results-panel {
  min-width: 0;
  padding: 26px 30px 36px;
}

.results-toolbar {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  margin-bottom: 18px;
}

.results-toolbar p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.results-toolbar p strong {
  color: var(--foreground);
  font-weight: 500;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}

.results-toolbar select {
  width: 165px;
}

.view-toggle {
  display: flex;
  padding-left: 10px;
  border-left: 1px solid var(--line);
}

.view-toggle button {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid #e1e2df;
  background: white;
  cursor: pointer;
}

.view-toggle button:first-child {
  border-radius: 7px 0 0 7px;
}

.view-toggle button:last-child {
  margin-left: -1px;
  border-radius: 0 7px 7px 0;
}

.view-toggle button.active {
  color: var(--foreground);
  background: #f2f2ef;
}

.competition-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.competition-card {
  position: relative;
  overflow: hidden;
  min-width: 0;
  border: 1px solid #e3e4e0;
  border-radius: 8px;
  background: white;
  box-shadow: 0 10px 28px rgba(24, 26, 29, 0.045);
}

.competition-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 40px rgba(24, 26, 29, 0.09);
}

.card-image {
  position: relative;
  height: 210px;
  overflow: hidden;
  background:
    linear-gradient(160deg, rgba(255,255,255,.18), transparent 38%),
    linear-gradient(145deg, #bac2b6, #e4e1d8);
}

.image-housing {
  background: linear-gradient(145deg, #c8ced0, #eee8de);
}

.image-square {
  background: linear-gradient(145deg, #707b68, #d5cbbd);
}

.image-civic {
  background: linear-gradient(145deg, #d5d2cb, #a7afb1);
}

.image-cultural {
  background: linear-gradient(145deg, #b8b0a5, #e8e4dc);
}

.image-landscape {
  background: linear-gradient(145deg, #6e7c63, #d4d6ca);
}

.architecture-shape {
  position: absolute;
  inset: 22% 8% 0;
  background:
    linear-gradient(90deg, transparent 0 9%, rgba(35,39,38,.86) 9% 11%, transparent 11% 23%, rgba(35,39,38,.86) 23% 25%, transparent 25% 100%),
    linear-gradient(180deg, #eceae3 0 72%, #b9b4a9 72% 76%, #6c7567 76% 100%);
  clip-path: polygon(0 32%, 42% 0, 100% 13%, 100% 100%, 0 100%);
  box-shadow: 0 16px 30px rgba(24, 26, 29, .18);
}

.architecture-shape::before {
  content: "";
  position: absolute;
  left: -14%;
  right: -14%;
  bottom: -12%;
  height: 28%;
  border-radius: 50%;
  background: rgba(72, 84, 65, 0.55);
  filter: blur(4px);
}

.freshness-badge {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  padding: 5px 9px;
  border-radius: 4px;
  background: rgba(31, 34, 34, 0.82);
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 10px;
  font-weight: 700;
  backdrop-filter: blur(8px);
}

.competition-card-body {
  position: relative;
  padding: 18px 17px 17px;
}

.card-heading-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.card-heading-row > div {
  min-width: 0;
  flex: 1;
}

.category-label {
  font-size: 10px;
}

.competition-card h3 {
  min-height: 52px;
  margin: 10px 0 0;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  font-size: 17px;
  line-height: 1.38;
  font-weight: 520;
  letter-spacing: -0.018em;
}

.bookmark-button {
  flex: none;
  margin-top: 0;
  border: 0;
  background: transparent;
  color: #5e6264;
  cursor: pointer;
}

.bookmark-button:hover {
  color: var(--accent);
  transform: translateY(-1px);
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-top: 14px;
  color: var(--muted);
  font-size: 11px;
}

.card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.card-meta svg {
  stroke-width: 1.7;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #efefec;
  color: var(--muted);
  font-size: 11px;
}

.card-footer strong {
  color: #424548;
  font-weight: 500;
  text-align: right;
}

.card-link {
  position: absolute;
  inset: 0;
  color: transparent;
}

.card-link svg {
  display: none;
}

.empty-state {
  min-height: 390px;
  display: grid;
  place-items: center;
  align-content: center;
  text-align: center;
  color: var(--muted);
}

.empty-state h2 {
  margin: 16px 0 4px;
  color: var(--foreground);
  font-size: 22px;
}

.empty-state p {
  margin: 0;
}

@media (max-width: 1180px) {
  .site-container {
    width: min(100% - 40px, 1120px);
  }

  .desktop-nav {
    gap: 24px;
  }

  .hero-grid {
    gap: 36px;
  }

  .stats-panel {
    width: 65%;
  }

  .competition-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .navbar {
    grid-template-columns: 1fr auto;
  }

  .desktop-nav {
    display: none;
  }

  .hero-grid {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .hero-copy {
    padding: 60px 0 0;
  }

  .hero-visual-wrap {
    padding-bottom: 0;
  }

  .stats-panel {
    position: relative;
    right: auto;
    bottom: auto;
    width: 100%;
    margin-top: -48px;
  }

  .listing-shell {
    grid-template-columns: 1fr;
  }

  .filters-panel {
    display: none;
  }
}

@media (max-width: 680px) {
  .site-container {
    width: min(100% - 28px, 620px);
  }

  .navbar {
    min-height: 68px;
  }

  .brand {
    gap: 10px;
  }

  .brand span {
    font-size: 11px;
    letter-spacing: 0.16em;
  }

  .navbar-actions .icon-button {
    display: none;
  }

  .primary-button.small {
    min-height: 38px;
    padding-inline: 16px;
  }

  .hero-copy {
    padding-top: 42px;
  }

  .hero-copy h1 {
    font-size: 46px;
  }

  .hero-description {
    font-size: 15px;
  }

  .search-row {
    align-items: stretch;
  }

  .hero-visual {
    height: 310px;
  }

  .stats-panel {
    grid-template-columns: repeat(2, 1fr);
    gap: 20px 0;
    padding: 22px 10px;
  }

  .stat:nth-child(3) {
    border-left: 0;
  }

  .listing-section {
    padding-top: 18px;
  }

  .listing-shell {
    overflow: visible;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .results-panel {
    padding: 0;
  }

  .results-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-actions {
    width: 100%;
  }

  .toolbar-actions > span,
  .view-toggle {
    display: none;
  }

  .results-toolbar select {
    width: 100%;
  }

  .competition-grid {
    grid-template-columns: 1fr;
  }
}
CSS

echo ""
echo "✓ Homepage criada com sucesso."
echo "✓ Backup guardado em: $BACKUP_DIR"
echo ""
echo "Agora executa:"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Certifica-te de que a API FastAPI está ativa em http://127.0.0.1:8000"
