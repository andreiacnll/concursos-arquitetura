const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


type Props = {
  params: {
    id: string;
  };
};


export default async function AnalisePage({
  params,
}: Props) {

  const { id } = await params;


  const resposta = await fetch(
    `${API_URL}/analise/${id}`,
    {
      cache: "no-store",
    }
  );


  if (!resposta.ok) {
    return (
      <main className="site-container">
        <h1>Análise não encontrada</h1>
      </main>
    );
  }


  const dados = await resposta.json();
  const ficha = dados.analise;


  return (
    <main className="site-container">


      <section className="page-header">

        <p className="eyebrow">
          ANÁLISE AUTOMÁTICA DE CONCURSO
        </p>


        <h1>
          {ficha.identificacao.titulo}
        </h1>


        <p>
          📍 {ficha.identificacao.local}
        </p>

      </section>



      <section className="analysis-intro">

        <h2>
          Visão geral
        </h2>


        <p>
          Este concurso corresponde a uma intervenção de
          reabilitação e modernização de um equipamento
          existente, envolvendo alteração funcional,
          coordenação de especialidades e intervenção
          arquitetónica sobre uma estrutura consolidada.
        </p>

      </section>




      <section className="analysis-grid">


        <article className="analysis-card">

          <span>
            📐 Área de intervenção
          </span>

          <strong>
            {ficha.programa.areas.total}
          </strong>

        </article>



        <article className="analysis-card">

          <span>
            💰 Valor da obra
          </span>

          <strong>
            {ficha.investimento.valor_obra}
          </strong>

        </article>



        <article className="analysis-card">

          <span>
            ⏱ Prazo de projeto
          </span>

          <strong>
            {ficha.investimento.prazo_projeto}
          </strong>

        </article>


      </section>





      <section className="analysis-section">

        <h2>
          Avaliação da complexidade
        </h2>


        <div className="complexity-box">

          <strong>
            ★★★★★
          </strong>


          <h3>
            {ficha.analise.complexidade}
          </h3>


          <ul>
            {ficha.analise.motivos.map(
              (motivo:string) => (
                <li key={motivo}>
                  {motivo}
                </li>
              )
            )}
          </ul>

        </div>

      </section>






      <section className="analysis-section">

        <h2>
          Entregáveis disponíveis
        </h2>


        <p>
          A documentação disponibilizada permite uma
          leitura aprofundada do contexto existente,
          programa funcional e condicionantes técnicas.
        </p>


        <div className="deliverables">

          {Object.entries(ficha.documentos).map(
            ([nome, existe]) => (

              existe && (

                <article key={nome}>

                  <strong>
                    ✓ {nome.replaceAll("_"," ")}
                  </strong>


                  <p>
                    Documento disponível para apoio ao
                    desenvolvimento do projeto.
                  </p>

                </article>

              )

            )
          )}

        </div>


      </section>






      <section className="analysis-section">

        <h2>
          Temas principais
        </h2>


        <div className="tags">

          {ficha.temas.map(
            (tema:string)=>(
              <span key={tema}>
                {tema}
              </span>
            )
          )}

        </div>

      </section>



    </main>
  );
}
