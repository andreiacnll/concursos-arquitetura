"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  CalendarDays,
  ChevronDown,
  Filter,
  Grid2X2,
  Landmark,
  List,
  Clock3,
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

const moreCategories = [
  "Paisagismo",
  "Cultura",
  "Equipamentos públicos",
  "Mobilidade",
  "Outros",
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
  if (
    text.includes("jardim") ||
    text.includes("parque") ||
    text.includes("paisag")
  )
    return "Paisagismo";

  if (
    text.includes("cultura") ||
    text.includes("teatro") ||
    text.includes("biblioteca") ||
    text.includes("centro cultural")
  )
    return "Cultura";

  if (
    text.includes("equipamento público") ||
    text.includes("equipamento municipal") ||
    text.includes("edifício municipal") ||
    text.includes("serviços municipais")
  )
    return "Equipamentos públicos";

  if (
    text.includes("mobilidade") ||
    text.includes("estação") ||
    text.includes("terminal") ||
    text.includes("metro") ||
    text.includes("ferrovi") ||
    text.includes("ciclovia")
  )
    return "Mobilidade";

  if (text.includes("patrim") || text.includes("museu")) return "Património";

  return "Outros";
}

function uniqueCount(values: Array<string | null | undefined>) {
  return new Set(values.filter(Boolean)).size;
}

const procedureOptions = [
  "Concurso público",
  "Concurso limitado por prévia qualificação",
  "Concurso de conceção",
  "Consulta prévia",
  "Ajuste direto",
];

const serviceOptions = [
  "Elaboração de projeto",
  "Revisão / Análise de projeto",
  "Concurso de conceção",
  "Fiscalização / Coordenação",
];

function normalizeText(value: string | null | undefined) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function matchesProcedure(
  concurso: Concurso,
  selectedProcedures: string[],
) {
  if (selectedProcedures.length === 0) return true;

  const source = normalizeText(concurso.tipo_procedimento);

  return selectedProcedures.some((procedure) =>
    source.includes(normalizeText(procedure)),
  );
}

function serviceForCompetition(concurso: Concurso) {
  const source = normalizeText(
    [concurso.titulo, concurso.tipo_procedimento]
      .filter(Boolean)
      .join(" "),
  );

  if (
    source.includes("fiscalizacao") ||
    source.includes("coordenacao de seguranca") ||
    source.includes("coordenacao")
  ) {
    return "Fiscalização / Coordenação";
  }

  if (
    source.includes("revisao") ||
    source.includes("analise de projeto") ||
    source.includes("verificacao de projeto")
  ) {
    return "Revisão / Análise de projeto";
  }

  if (
    source.includes("concurso de concecao") ||
    source.includes("concurso de concepcao")
  ) {
    return "Concurso de conceção";
  }

  if (
    source.includes("elaboracao de projeto") ||
    source.includes("projeto de arquitetura") ||
    source.includes("projecto de arquitectura") ||
    source.includes("projeto")
  ) {
    return "Elaboração de projeto";
  }

  return null;
}

function matchesService(concurso: Concurso, selectedServices: string[]) {
  if (selectedServices.length === 0) return true;

  const service = serviceForCompetition(concurso);
  return service !== null && selectedServices.includes(service);
}


function parseCompetitionDate(value?: string | null) {
  if (!value) return null;

  const cleanValue = String(value).trim();

  // Formato YYYY-MM-DD, evitando alterações por fuso horário
  const isoMatch = cleanValue.match(/^(\d{4})-(\d{2})-(\d{2})/);

  if (isoMatch) {
    const [, year, month, day] = isoMatch;

    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      12,
      0,
      0,
      0,
    );
  }

  // Formatos DD-MM-YYYY, DD/MM/YYYY e DD.MM.YYYY
  const portugueseMatch = cleanValue.match(
    /^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/,
  );

  if (portugueseMatch) {
    const [, day, month, year] = portugueseMatch;

    const parsedDate = new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      12,
      0,
      0,
      0,
    );

    return Number.isNaN(parsedDate.getTime()) ? null : parsedDate;
  }

  const parsedDate = new Date(cleanValue);

  return Number.isNaN(parsedDate.getTime()) ? null : parsedDate;
}

function isPublishedInLast7Days(value?: string | null) {
  const publicationDate = parseCompetitionDate(value);

  if (!publicationDate) return false;

  publicationDate.setHours(0, 0, 0, 0);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Hoje + seis dias anteriores = sete dias de calendário
  const firstDay = new Date(today);
  firstDay.setDate(today.getDate() - 6);

  return publicationDate >= firstDay && publicationDate <= today;
}

export default function CompetitionsDashboard({
  concursos,
}: {
  concursos: Concurso[];
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Todos");
  const [moreCategoriesOpen, setMoreCategoriesOpen] = useState(false);
  const [district, setDistrict] = useState("Todos os distritos");
  const [sort, setSort] = useState("recentes");
  const [selectedProcedures, setSelectedProcedures] = useState<string[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [activeTab, setActiveTab] = useState<"todos" | "favoritos">("todos");
  const [statFilter, setStatFilter] = useState<
    "todos" | "ativos" | "novos" | "terminam" | "entidades"
  >("todos");
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [favoritesLoaded, setFavoritesLoaded] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("concursos-favoritos");
      const parsed = stored ? JSON.parse(stored) : [];

      if (Array.isArray(parsed)) {
        setFavoriteIds(parsed.map(String));
      }
    } catch {
      setFavoriteIds([]);
    } finally {
      setFavoritesLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!favoritesLoaded) return;

    window.localStorage.setItem(
      "concursos-favoritos",
      JSON.stringify(favoriteIds),
    );
  }, [favoriteIds, favoritesLoaded]);

  function toggleFavorite(id: Concurso["id"]) {
    const favoriteId = String(id);

    setFavoriteIds((current) =>
      current.includes(favoriteId)
        ? current.filter((item) => item !== favoriteId)
        : [...current, favoriteId],
    );
  }

  function toggleProcedure(procedure: string) {
    setSelectedProcedures((current) =>
      current.includes(procedure)
        ? current.filter((item) => item !== procedure)
        : [...current, procedure],
    );
  }

  function toggleService(service: string) {
    setSelectedServices((current) =>
      current.includes(service)
        ? current.filter((item) => item !== service)
        : [...current, service],
    );
  }

  function clearFilters() {
    setQuery("");
    setCategory("Todos");
    setDistrict("Todos os distritos");
    setSelectedProcedures([]);
    setSelectedServices([]);
  }

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
      const matchesFavorites =
        activeTab === "todos" || favoriteIds.includes(String(item.id));

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
      const matchesSelectedProcedure = matchesProcedure(
        item,
        selectedProcedures,
      );
      const matchesSelectedService = matchesService(item, selectedServices);

      const deadlineDate = item.data_limite
        ? new Date(item.data_limite)
        : null;

      const todayFilter = new Date();
      todayFilter.setHours(0, 0, 0, 0);

      const sevenDaysAheadFilter = new Date(todayFilter);
      sevenDaysAheadFilter.setDate(todayFilter.getDate() + 7);
      sevenDaysAheadFilter.setHours(23, 59, 59, 999);

      const matchesStatFilter =
        statFilter === "todos" ||
        (statFilter === "ativos" && item.estado === "aberto") ||
        (statFilter === "novos" && isPublishedInLast7Days(item.data_publicacao_iso ?? item.data)) ||
        (statFilter === "terminam" &&
          deadlineDate !== null &&
          !Number.isNaN(deadlineDate.getTime()) &&
          deadlineDate >= todayFilter &&
          deadlineDate <= sevenDaysAheadFilter) ||
        (statFilter === "entidades" && Boolean(item.entidade));

      return (
        matchesFavorites &&
        matchesQuery &&
        matchesCategory &&
        matchesDistrict &&
        matchesSelectedProcedure &&
        matchesSelectedService &&
        matchesStatFilter
      );
    });

    return [...items].sort((a, b) => {
      const parsedDateA = parseCompetitionDate(
        a.data_publicacao_iso ?? a.data,
      );
      const parsedDateB = parseCompetitionDate(
        b.data_publicacao_iso ?? b.data,
      );

      const dateA = parsedDateA?.getTime() ?? 0;
      const dateB = parsedDateB?.getTime() ?? 0;

      return sort === "antigos" ? dateA - dateB : dateB - dateA;
    });
  }, [
    concursos,
    query,
    category,
    district,
    selectedProcedures,
    selectedServices,
    sort,
    activeTab,
    favoriteIds,
    statFilter,
  ]);

  const newThisWeek = concursos.filter((item) =>
    isPublishedInLast7Days(item.data_publicacao_iso ?? item.data),
  ).length;

  const active = concursos.filter((item) => item.estado === "aberto").length;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const sevenDaysAhead = new Date(today);
  sevenDaysAhead.setDate(today.getDate() + 7);
  sevenDaysAhead.setHours(23, 59, 59, 999);

  const endingSoon = concursos.filter((item) => {
    if (!item.data_limite) return false;

    const deadline = new Date(item.data_limite);

    return (
      !Number.isNaN(deadline.getTime()) &&
      deadline >= today &&
      deadline <= sevenDaysAhead
    );
  }).length;

  const entityCount = uniqueCount(concursos.map((item) => item.entidade));

  function applyStatFilter(
    filter: "todos" | "ativos" | "novos" | "terminam" | "entidades",
  ) {
    const nextFilter = statFilter === filter ? "todos" : filter;

    setStatFilter(nextFilter);
    setActiveTab("todos");
    setQuery("");
    setCategory("Todos");
    setDistrict("Todos os distritos");
    setSelectedProcedures([]);
    setSelectedServices([]);

    window.requestAnimationFrame(() => {
      window.setTimeout(() => {
        const resultsSection = document.getElementById("concursos");

        if (resultsSection) {
          resultsSection.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }
      }, 100);
    });
  }

  return (
    <>
      <section className="hero-section">
        <div className="site-container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">Concursos públicos</p>
            <h1>
              Plataforma de
              <br />
              acompanhamento de concursos
            </h1>
            <p className="hero-description">
              Consulta, pesquisa e acompanhamento de concursos públicos de
              arquitetura, urbanismo e paisagismo em Portugal.
            </p>

            <div className="search-row">
              <label className="search-box">
                <Search size={20} strokeWidth={1.8} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Pesquisar por entidade, município ou palavra-chave..."
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
              <div className="more-categories">
                <button
                  type="button"
                  className={
                    moreCategories.includes(category) ||
                    moreCategoriesOpen
                      ? "active"
                      : ""
                  }
                  aria-expanded={moreCategoriesOpen}
                  aria-haspopup="menu"
                  onClick={() =>
                    setMoreCategoriesOpen((current) => !current)
                  }
                >
                  {moreCategories.includes(category) ? category : "Mais"}

                  <ChevronDown
                    size={15}
                    className={moreCategoriesOpen ? "is-open" : ""}
                  />
                </button>

                {moreCategoriesOpen && (
                  <div
                    className="more-categories-menu"
                    role="menu"
                    aria-label="Mais categorias"
                  >
                    {moreCategories.map((item) => (
                      <button
                        key={item}
                        type="button"
                        role="menuitem"
                        className={category === item ? "active" : ""}
                        onClick={() => {
                          setCategory(item);
                          setMoreCategoriesOpen(false);
                        }}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="hero-visual-wrap">
            <div className="hero-visual" />
          </div>

        </div>

        <div className="site-container stats-container">
          <div className="stats-panel">
            <button
              type="button"
              className={`stat ${statFilter === "ativos" ? "active" : ""}`}
              onClick={() => applyStatFilter("ativos")}
              title="Ver todos os concursos ativos"
              aria-pressed={statFilter === "ativos"}
            >
              <Building2 />
              <div>
                <strong>{active || concursos.length}</strong>
                <span>Concursos ativos</span>
              </div>
            </button>

            <button
              type="button"
              className={`stat ${statFilter === "novos" ? "active" : ""}`}
              onClick={() => applyStatFilter("novos")}
              title="Ver concursos publicados nos últimos 7 dias"
              aria-pressed={statFilter === "novos"}
            >
              <CalendarDays />
              <div>
                <strong>{newThisWeek}</strong>
                <span>Novos esta semana</span>
              </div>
            </button>

            <button
              type="button"
              className={`stat ${statFilter === "terminam" ? "active" : ""}`}
              onClick={() => applyStatFilter("terminam")}
              title="Ver concursos que terminam nos próximos 7 dias"
              aria-pressed={statFilter === "terminam"}
            >
              <Clock3 />
              <div>
                <strong>{endingSoon}</strong>
                <span>Terminam em 7 dias</span>
              </div>
            </button>

            <button
              type="button"
              className={`stat ${statFilter === "entidades" ? "active" : ""}`}
              onClick={() => applyStatFilter("entidades")}
              title="Ver concursos com entidade identificada"
              aria-pressed={statFilter === "entidades"}
            >
              <Landmark />
              <div>
                <strong>{entityCount}</strong>
                <span>Entidades públicas</span>
              </div>
            </button>
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
              {procedureOptions.map((label) => (
                <label className="check-row" key={label}>
                  <input
                    type="checkbox"
                    checked={selectedProcedures.includes(label)}
                    onChange={() => toggleProcedure(label)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="filter-group">
              <p>Tipo de serviço</p>
              {serviceOptions.map((label) => (
                <label className="check-row" key={label}>
                  <input
                    type="checkbox"
                    checked={selectedServices.includes(label)}
                    onChange={() => toggleService(label)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="filter-group">
              <button
                type="button"
                className="clear-filters-button"
                onClick={clearFilters}
              >
                Limpar filtros
              </button>
            </div>
          </aside>

          <div className="results-panel">
            <div className="results-toolbar">
              <div className="results-toolbar-left">
                <div className="results-tabs" role="tablist" aria-label="Concursos">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "todos"}
                    className={activeTab === "todos" ? "active" : ""}
                    onClick={() => setActiveTab("todos")}
                  >
                    Todos
                  </button>

                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "favoritos"}
                    className={activeTab === "favoritos" ? "active" : ""}
                    onClick={() => setActiveTab("favoritos")}
                  >
                    Favoritos
                    <span>{favoriteIds.length}</span>
                  </button>
                </div>

                <p>
                  <strong>{filtered.length}</strong>{" "}
                  {activeTab === "favoritos"
                    ? "favoritos encontrados"
                    : "concursos encontrados"}
                </p>
              </div>

              <div className="toolbar-actions">
                <span>Ordenar por</span>
                <select value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="recentes">Mais recentes</option>
                  <option value="antigos">Mais antigos</option>
                </select>
                <div className="view-toggle">
                  <button
                    type="button"
                    className={view === "grid" ? "active" : ""}
                    aria-label="Vista em grelha"
                    aria-pressed={view === "grid"}
                    onClick={() => setView("grid")}
                  >
                    <Grid2X2 size={18} />
                  </button>
                  <button
                    type="button"
                    className={view === "list" ? "active" : ""}
                    aria-label="Vista em lista"
                    aria-pressed={view === "list"}
                    onClick={() => setView("list")}
                  >
                    <List size={19} />
                  </button>
                </div>
              </div>
            </div>

            {filtered.length > 0 ? (
              <div
                className={`competition-grid ${
                  view === "list" ? "is-list" : ""
                }`}
              >
                {filtered.map((concurso, index) => (
                  <CompetitionCard
                    key={concurso.id}
                    concurso={concurso}
                    index={index}
                    isFavorite={favoriteIds.includes(String(concurso.id))}
                    onToggleFavorite={() => toggleFavorite(concurso.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <SlidersHorizontal size={28} />
                <h2>
                  {activeTab === "favoritos"
                    ? "Ainda não tens favoritos"
                    : "Não encontrámos concursos"}
                </h2>
                <p>
                  {activeTab === "favoritos"
                    ? "Clica na bandeirinha de um concurso para o guardar aqui."
                    : "Experimenta alterar a pesquisa ou os filtros selecionados."}
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}
