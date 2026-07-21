"use client";

import { useMemo, useState } from "react";
import SearchBar from "./SearchBar";

type Estado = "aberto" | "encerrado" | "sem_prazo";
type Filtro = "todos" | "aberto" | "encerrado";

type Concurso = {
  id: number;
  titulo: string;
  entidade: string;
  link: string;
  data: string;
  relevante: number;
  data_limite: string | null;
  preco_base: string | null;
  estado: Estado;
};

type ConcursosListProps = {
  concursos: Concurso[];
};

function temValor(valor: string | null) {
  return valor !== null && valor.trim() !== "";
}

function estilosEstado(estado: Estado) {
  if (estado === "aberto") {
    return {
      texto: "Aberto",
      classe: "bg-emerald-100 text-emerald-700",
      barra: "bg-emerald-500",
    };
  }

  if (estado === "encerrado") {
    return {
      texto: "Encerrado",
      classe: "bg-red-100 text-red-700",
      barra: "bg-red-500",
    };
  }

  return {
    texto: "Prazo não indicado",
    classe: "bg-amber-100 text-amber-700",
    barra: "bg-amber-500",
  };
}

export default function ConcursosList({
  concursos,
}: ConcursosListProps) {
  const [pesquisa, setPesquisa] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");

  const concursosFiltrados = useMemo(() => {
    const textoPesquisa = pesquisa.trim().toLowerCase();

    return concursos.filter((concurso) => {
      const titulo = concurso.titulo?.toLowerCase() ?? "";
      const entidade = concurso.entidade?.toLowerCase() ?? "";

      const correspondePesquisa =
        titulo.includes(textoPesquisa) ||
        entidade.includes(textoPesquisa);

      const correspondeFiltro =
        filtro === "todos" || concurso.estado === filtro;

      return correspondePesquisa && correspondeFiltro;
    });
  }, [concursos, pesquisa, filtro]);

  return (
    <div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <SearchBar value={pesquisa} onChange={setPesquisa} />

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setFiltro("todos")}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              filtro === "todos"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Todos
          </button>

          <button
            type="button"
            onClick={() => setFiltro("aberto")}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              filtro === "aberto"
                ? "bg-emerald-600 text-white"
                : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
            }`}
          >
            🟢 Abertos
          </button>

          <button
            type="button"
            onClick={() => setFiltro("encerrado")}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              filtro === "encerrado"
                ? "bg-red-600 text-white"
                : "bg-red-50 text-red-700 hover:bg-red-100"
            }`}
          >
            🔴 Encerrados
          </button>
        </div>
      </div>

      <div className="mb-5 mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">
          <span className="font-semibold text-slate-800">
            {concursosFiltrados.length}
          </span>{" "}
          oportunidades encontradas
        </p>

        {(pesquisa !== "" || filtro !== "todos") && (
          <button
            type="button"
            onClick={() => {
              setPesquisa("");
              setFiltro("todos");
            }}
            className="text-left text-sm font-semibold text-blue-600 transition hover:text-blue-700"
          >
            Limpar filtros
          </button>
        )}
      </div>

      <div className="grid gap-5">
        {concursosFiltrados.map((concurso) => {
          const estado = estilosEstado(concurso.estado);

          return (
            <article
              key={concurso.id}
              className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition duration-200 hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg"
            >
              <div className={`h-1.5 w-full ${estado.barra}`} />

              <div className="p-5 sm:p-6">
                <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="mb-4 flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-bold ${estado.classe}`}
                      >
                        {estado.texto}
                      </span>

                      {concurso.relevante === 1 && (
                        <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-700">
                          ✨ Relevante
                        </span>
                      )}

                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        📅 Publicado em{" "}
                        {concurso.data || "Data não indicada"}
                      </span>
                    </div>

                    <h3 className="text-xl font-bold leading-snug text-slate-950 transition group-hover:text-blue-700 sm:text-2xl">
                      {concurso.titulo}
                    </h3>

                    <div className="mt-4 flex items-start gap-2 text-slate-600">
                      <span aria-hidden="true">🏢</span>

                      <p className="font-medium">
                        {concurso.entidade || "Entidade não indicada"}
                      </p>
                    </div>

                    <div className="mt-6 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                          Prazo
                        </p>

                        <p className="mt-2 font-semibold text-slate-800">
                          ⏳{" "}
                          {temValor(concurso.data_limite)
                            ? concurso.data_limite
                            : "Não indicado"}
                        </p>
                      </div>

                      <div className="rounded-xl bg-slate-50 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                          Preço base
                        </p>

                        <p className="mt-2 font-semibold text-slate-800">
                          💶{" "}
                          {temValor(concurso.preco_base)
                            ? concurso.preco_base
                            : "Não indicado"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <a
                    href={concurso.link}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                  >
                    Ver concurso
                    <span aria-hidden="true">↗</span>
                  </a>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {concursosFiltrados.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
          <div className="text-4xl">🔎</div>

          <h3 className="mt-4 text-lg font-bold text-slate-900">
            Nenhum concurso encontrado
          </h3>

          <p className="mt-2 text-sm text-slate-500">
            Experimenta alterar a pesquisa ou limpar os filtros.
          </p>

          <button
            type="button"
            onClick={() => {
              setPesquisa("");
              setFiltro("todos");
            }}
            className="mt-5 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            Limpar filtros
          </button>
        </div>
      )}
    </div>
  );
}
