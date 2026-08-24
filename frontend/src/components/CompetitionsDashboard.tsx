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
import CompetitionFiltersSidebar from "./CompetitionFiltersSidebar";
import type { Concurso } from "./competition-types";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";
import {
  ANALYSIS_POLL_INTERVAL_MS,
  fetchAnalysisJobState,
  isActiveAnalysisStatus,
  normalizeAnalysisJob,
} from "@/lib/analysis-jobs";
import {
  compareCompetitions,
  DEFAULT_COMPETITION_FILTERS,
  getCompetitionPriceRange,
  hasActiveCompetitionFilters,
  matchesAdvancedFilters,
  type CompetitionSort,
} from "./competition-filters";

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

type AnaliseResumo = {
  id?: number;
  concurso_id: number;
  estado: string;
};

type AnaliseEstado = {
  tem_analise: boolean;
  estado: string | null;
  stage?: string | null;
  job_id?: number | null;
  analise_id?: number | null;
};

function parseDataEntrega(valor?: string | null) {
  if (!valor) return null;

  const cleanValue = String(valor).trim();

  // API: YYYY-MM-DD
  const iso = cleanValue.match(/^(\d{4})-(\d{2})-(\d{2})/);

  if (iso) {
    const [, ano, mes, dia] = iso;

    return new Date(
      Number(ano),
      Number(mes) - 1,
      Number(dia),
      12,
      0,
      0,
      0,
    );
  }

  // Portugal: DD-MM-YYYY / DD/MM/YYYY / DD.MM.YYYY
  const pt = cleanValue.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})/);

  if (pt) {
    const [, dia, mes, ano] = pt;

    return new Date(
      Number(ano),
      Number(mes) - 1,
      Number(dia),
      12,
      0,
      0,
      0,
    );
  }

  return null;
}

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

function formatPriceFilter(value: number) {
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
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

function competitionRecencyValue(concurso: Concurso) {
  const extended = concurso as Concurso & {
    data_ordenacao_iso?: string | null;
    first_seen_at?: string | null;
  };

  const candidates = [
    concurso.data_publicacao_iso,
    concurso.data,
    extended.data_ordenacao_iso,
    extended.first_seen_at,
  ];

  return candidates.find((value) => parseCompetitionDate(value) !== null) || null;
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
  concursos: concursosIniciais,
}: {
  concursos: Concurso[];
}) {
  const [concursos, setConcursos] = useState<Concurso[]>(concursosIniciais);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Todos");
  const [moreCategoriesOpen, setMoreCategoriesOpen] = useState(false);
  const [district, setDistrict] = useState("Todos os distritos");
  const [sort, setSort] = useState<CompetitionSort>("recentes");
  const [selectedProcedures, setSelectedProcedures] = useState<string[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [activeTab, setActiveTab] = useState<"todos" | "favoritos">("todos");
  const [statFilter, setStatFilter] = useState<
    "todos" | "ativos" | "novos" | "terminam" | "entidades"
  >("todos");
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [analisesMap, setAnalisesMap] = useState<Record<string, AnaliseEstado>>({});
  const { user, session } = useAuth();

  useEffect(() => {
    setConcursos(concursosIniciais);
  }, [concursosIniciais]);

  // Filtros adicionais
  const [precoMin, setPrecoMin] = useState("");
  const [precoMax, setPrecoMax] = useState("");
  const [entidadeQuery, setEntidadeQuery] = useState("");
  const [prazoFilter, setPrazoFilter] = useState<"todos" | "7" | "15" | "30">("todos");

  const priceRange = useMemo(
    () => getCompetitionPriceRange(concursos),
    [concursos],
  );
  const priceScaleMin = priceRange ? Math.min(0, priceRange.min) : 0;
  const selectedPriceMin = priceRange
    ? Math.max(
        priceScaleMin,
        Math.min(Number(precoMin || priceScaleMin), priceRange.max),
      )
    : 0;
  const selectedPriceMax = priceRange
    ? Math.max(
        selectedPriceMin,
        Math.min(Number(precoMax || priceRange.max), priceRange.max),
      )
    : 0;

  useEffect(() => {
    const map: Record<string, AnaliseEstado> = {};
    concursos.forEach((concurso) => {
      if (concurso.temAnalise) {
        map[String(concurso.id)] = {
          tem_analise: true,
          estado: concurso.estadoAnalise ?? "concluida",
          analise_id: concurso.analiseId,
        };
      }
    });
    setAnalisesMap(map);
  }, [concursos]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    const carregarAnalises = () => fetch(`${API_URL}/analises`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Não foi possível carregar as análises.");
        return res.json();
      })
      .then((dados: unknown) => {
        let lista: AnaliseResumo[] = [];
        if (Array.isArray(dados)) lista = dados as AnaliseResumo[];
        else if (dados && typeof dados === 'object') {
          const obj = dados as Record<string, unknown>;
          lista = (obj.analises || obj.items || obj.resultados || []) as AnaliseResumo[];
        }
        const map: Record<string, AnaliseEstado> = {};
        lista.forEach((a) => {
          const job = normalizeAnalysisJob(a);
          map[String(a.concurso_id)] = {
            tem_analise: true,
            estado: job?.status || a.estado || "aguarda",
            stage: job?.stage || null,
            job_id: job?.job_id || null,
            analise_id: job?.analysis_id || a.id,
          };
        });
        setAnalisesMap(map);
      })
      .catch(() => {});

    carregarAnalises();

    const onFocus = () => carregarAnalises();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [session?.access_token]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    const activeJobs = Object.values(analisesMap).filter(
      (item) => item.job_id && isActiveAnalysisStatus(item.estado),
    );
    if (activeJobs.length === 0) return;

    const timer = window.setInterval(() => {
      activeJobs.forEach((item) => {
        if (!item.job_id) return;
        fetchAnalysisJobState(token, item.job_id)
          .then((job) => {
            setAnalisesMap((current) => ({
              ...current,
              [String(job.concurso_id)]: {
                tem_analise: true,
                estado: job.status,
                stage: job.stage,
                job_id: job.job_id,
                analise_id: job.analysis_id,
              },
            }));

            if (!isActiveAnalysisStatus(job.status)) {
              void atualizarConcursoNoEcra(String(job.concurso_id));
            }
          })
          .catch(() => {});
      });
    }, ANALYSIS_POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [analisesMap, session?.access_token]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    fetch(`${API_URL}/favoritos`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Não foi possível carregar os favoritos.");
        return res.json();
      })
      .then((dados: { favoritos?: Array<{ concurso_id: number }> }) => {
        setFavoriteIds(
          (dados.favoritos ?? []).map((favorito) =>
            String(favorito.concurso_id),
          ),
        );
      })
      .catch(() => {});
  }, [session?.access_token]);

  function toggleFavorite(id: Concurso["id"]) {
    const token = session?.access_token;
    if (!user || !token) return;

    const favoriteId = String(id);
    const isAdding = !favoriteIds.includes(favoriteId);

    setFavoriteIds((current) =>
      isAdding
        ? [...current, favoriteId]
        : current.filter((item) => item !== favoriteId),
    );

    fetch(`${API_URL}/favoritos/${favoriteId}`, {
      method: isAdding ? "POST" : "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Não foi possível atualizar o favorito.");
      })
      .catch(() => {
        setFavoriteIds((current) =>
          isAdding
            ? current.filter((item) => item !== favoriteId)
            : [...current, favoriteId],
        );
      });
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

  async function atualizarConcursoNoEcra(id: string) {
    const token = session?.access_token;
    const response = await fetch(
      `${API_URL}/concursos/${id}?fresh=${Date.now()}`,
      {
        cache: "no-store",
        headers: token
          ? { Authorization: `Bearer ${token}` }
          : undefined,
      },
    );

    if (!response.ok) return;

    const atualizado = (await response.json()) as Concurso;
    setConcursos((current) =>
      current.map((item) =>
        String(item.id) === String(atualizado.id)
          ? { ...item, ...atualizado }
          : item,
      ),
    );
  }

  async function criarAnalise(id: string) {
    const token = session?.access_token;
    if (!token) {
      throw new Error("A sessão terminou. Volta a iniciar sessão.");
    }

    const response = await fetch(`${API_URL}/analises/criar`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ concurso_id: Number(id) }),
    });

    if (!response.ok) {
      const dados = await response.json().catch(() => null);
      throw new Error(
        dados?.detail || "Não foi possível colocar a análise na fila.",
      );
    }

    const job = normalizeAnalysisJob(await response.json());
    setAnalisesMap((current) => ({
      ...current,
      [id]: {
        tem_analise: true,
        estado: job?.status || "queued",
        stage: job?.stage || "queued",
        job_id: job?.job_id || null,
        analise_id: job?.analysis_id || null,
      },
    }));
  }

  function clearFilters() {
    setQuery("");
    setCategory("Todos");
    setDistrict("Todos os distritos");
    setSelectedProcedures([]);
    setSelectedServices([]);
    setPrecoMin("");
    setPrecoMax("");
    setEntidadeQuery("");
    setPrazoFilter("todos");
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
      const matchesAdditional = matchesAdvancedFilters(item, {
        precoMin: precoMin === "" ? "" : String(selectedPriceMin),
        precoMax: precoMax === "" ? "" : String(selectedPriceMax),
        entidadeQuery,
        prazoFilter,
      });

      const deadlineDate = parseDataEntrega(
        item.data_fim_calculada,
      );

      const todayFilter = new Date();
      todayFilter.setHours(0, 0, 0, 0);

      const sevenDaysAheadFilter = new Date(todayFilter);
      sevenDaysAheadFilter.setDate(todayFilter.getDate() + 7);
      sevenDaysAheadFilter.setHours(23, 59, 59, 999);

      const matchesStatFilter =
        statFilter === "todos" ||
        (statFilter === "ativos" && item.estado === "aberto") ||
        (statFilter === "novos" &&
          isPublishedInLast7Days(competitionRecencyValue(item))) ||
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
        matchesAdditional &&
        matchesStatFilter
      );
    });

    return [...items].sort((a, b) => {
      if (sort === "recentes") {
        const aDate = parseCompetitionDate(competitionRecencyValue(a));
        const bDate = parseCompetitionDate(competitionRecencyValue(b));
        const dateDifference =
          (bDate?.getTime() || 0) - (aDate?.getTime() || 0);
        if (dateDifference !== 0) return dateDifference;
      }
      return compareCompetitions(a, b, sort);
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
    precoMin,
    precoMax,
    selectedPriceMin,
    selectedPriceMax,
    entidadeQuery,
    prazoFilter,
  ]);

  const newThisWeek = concursos.filter((item) =>
    isPublishedInLast7Days(competitionRecencyValue(item)),
  ).length;

  const active = concursos.filter((item) => item.estado === "aberto").length;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const sevenDaysAhead = new Date(today);
  sevenDaysAhead.setDate(today.getDate() + 7);
  sevenDaysAhead.setHours(23, 59, 59, 999);

  const endingSoon = concursos.filter((item) => {
    const deadline = parseDataEntrega(
      item.data_fim_calculada,
    );

    if (!deadline || Number.isNaN(deadline.getTime())) {
      return false;
    }

    const deadlineDay = new Date(
      deadline.getFullYear(),
      deadline.getMonth(),
      deadline.getDate(),
    );

    const todayDay = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate(),
    );

    const diffDays = Math.ceil(
      (deadlineDay.getTime() - todayDay.getTime()) /
      (1000 * 60 * 60 * 24)
    );

    return diffDays >= 0 && diffDays <= 7;
  }).length;

  const entityCount = uniqueCount(concursos.map((item) => item.entidade));
  const filtersState = {
    district,
    precoMin,
    precoMax,
    entidadeQuery,
    prazoFilter,
    selectedProcedures,
    selectedServices,
  };
  const hasActiveFilters = hasActiveCompetitionFilters(filtersState);

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
    setPrecoMin("");
    setPrecoMax("");
    setEntidadeQuery("");
    setPrazoFilter("todos");

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
            <p className="eyebrow">Pesquisa de concursos</p>
            <h1>
              Encontra o
              <br />
              concurso certo
            </h1>
            <p className="hero-description">
              Pesquisa concursos públicos de arquitetura, urbanismo e
              paisagismo em Portugal. Filtra por categoria, distrito,
              tipo de procedimento e muito mais.
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
          <CompetitionFiltersSidebar
            items={concursos}
            districts={districts}
            filters={filtersState}
            onChange={(next) => {
              setDistrict(next.district);
              setPrecoMin(next.precoMin);
              setPrecoMax(next.precoMax);
              setEntidadeQuery(next.entidadeQuery);
              setPrazoFilter(next.prazoFilter);
              setSelectedProcedures(next.selectedProcedures);
              setSelectedServices(next.selectedServices);
            }}
            onClear={clearFilters}
            hasActiveFilters={hasActiveFilters}
          />
          <aside className="filters-panel filters-panel-legacy-hidden" aria-hidden="true">
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
              <p>Intervalo de preço</p>
              {priceRange ? (
                <div className="dynamic-price-filter">
                  <div className="dynamic-price-values">
                    <strong>{formatPriceFilter(selectedPriceMin)}</strong>
                    <strong>{formatPriceFilter(selectedPriceMax)}</strong>
                  </div>
                  <div
                    className="dynamic-price-slider"
                    style={{
                      "--price-start": `${
                        ((selectedPriceMin - priceScaleMin) /
                          Math.max(priceRange.max - priceScaleMin, 1)) *
                        100
                      }%`,
                      "--price-end": `${
                        ((selectedPriceMax - priceScaleMin) /
                          Math.max(priceRange.max - priceScaleMin, 1)) *
                        100
                      }%`,
                    } as React.CSSProperties}
                  >
                    <input
                      type="range"
                      min={priceScaleMin}
                      max={priceRange.max}
                      step="any"
                      value={selectedPriceMin}
                      aria-label="Valor mínimo"
                      onChange={(event) =>
                        setPrecoMin(
                          String(
                            Math.min(
                              Number(event.target.value),
                              selectedPriceMax,
                            ),
                          ),
                        )
                      }
                    />
                    <input
                      type="range"
                      min={priceScaleMin}
                      max={priceRange.max}
                      step="any"
                      value={selectedPriceMax}
                      aria-label="Valor máximo"
                      onChange={(event) =>
                        setPrecoMax(
                          String(
                            Math.max(
                              Number(event.target.value),
                              selectedPriceMin,
                            ),
                          ),
                        )
                      }
                    />
                  </div>
                  <div className="dynamic-price-extremes">
                    <span>{formatPriceFilter(priceScaleMin)}</span>
                    <span>{formatPriceFilter(priceRange.max)}</span>
                  </div>
                  <small>
                    {priceRange.count} concursos com valor · menor valor
                    encontrado: {formatPriceFilter(priceRange.min)}
                  </small>
                </div>
              ) : (
                <p className="dynamic-price-empty">
                  Sem valores disponíveis nos concursos atuais.
                </p>
              )}
            </div>

            <div className="filter-group">
              <label htmlFor="entity-filter">Entidade promotora</label>
              <input
                id="entity-filter"
                className="filter-text-input"
                value={entidadeQuery}
                onChange={(event) => setEntidadeQuery(event.target.value)}
                placeholder="Pesquisar entidade"
              />
            </div>

            <div className="filter-group">
              <label htmlFor="deadline-filter">Prazo de entrega</label>
              <select
                id="deadline-filter"
                value={prazoFilter}
                onChange={(event) =>
                  setPrazoFilter(
                    event.target.value as "todos" | "7" | "15" | "30",
                  )
                }
              >
                <option value="todos">Todos os prazos</option>
                <option value="7">Próximos 7 dias</option>
                <option value="15">Próximos 15 dias</option>
                <option value="30">Próximos 30 dias</option>
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
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as CompetitionSort)}
                >
                  <option value="recentes">Mais recentes</option>
                  <option value="antigos">Mais antigos</option>
                  <option value="prazo">Prazo mais próximo</option>
                  <option value="valor_desc">Valor mais elevado</option>
                  <option value="valor_asc">Valor mais baixo</option>
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
                    temAnalise={
                      analisesMap[String(concurso.id)]?.tem_analise ??
                      concurso.temAnalise
                    }
                    analiseEstado={
                      analisesMap[String(concurso.id)]?.estado ??
                      concurso.estadoAnalise ??
                      undefined
                    }
                    analiseStage={
                      analisesMap[String(concurso.id)]?.stage ??
                      undefined
                    }
                    onCriarAnalise={() => criarAnalise(String(concurso.id))}
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
