type Concurso = {
  id: number;
  titulo: string;
  entidade: string;
  data_limite: string | null;
};

async function getConcursos(): Promise<Concurso[]> {
  const res = await fetch("http://127.0.0.1:8000/concursos", {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Erro ao carregar concursos");
  }

 const data = await res.json();
return data.resultados;
}

export default async function Home() {
  const concursos = await getConcursos();

  return (
    <main className="min-h-screen bg-gray-100 p-10">
      <h1 className="text-4xl font-bold text-blue-700">
        ArquiConcursos
      </h1>

      <p className="mt-4 mb-8 text-gray-600">
        Plataforma de concursos públicos para arquitetos.
      </p>

      <div className="space-y-4">
        {concursos.map((concurso) => (
          <div
            key={concurso.id}
            className="rounded-lg bg-white p-5 shadow"
          >
            <h2 className="text-xl font-semibold">
              {concurso.titulo}
            </h2>

            <p>{concurso.entidade}</p>

            <p className="text-sm text-gray-500">
              Prazo: {concurso.data_limite ?? "Sem informação"}
            </p>
          </div>
        ))}
      </div>
    </main>
  );
}