import MostrarMais from "@/components/MostrarMais";

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

        <div className="analysis-cover">
          <img
            src="/analises/450837-capa.png"
            alt="Peça desenhada do concurso"
          />
        </div>


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




      <section className="analysis-section">

        <h2>
          Programa preliminar
        </h2>


        <p>
          O programa preliminar define uma intervenção profunda sobre
          um equipamento municipal existente, procurando recuperar
          o papel do Mercado Municipal enquanto espaço comercial,
          social e de encontro urbano.

          A proposta deverá responder às atuais exigências de
          conforto, acessibilidade e funcionamento, mantendo a
          identidade do edifício e introduzindo novas dinâmicas
          de utilização.
        </p>


        <MostrarMais>

          <h3>
            Contexto existente
          </h3>

          <p>
            O edifício desenvolve-se em três pisos, com diferentes
            áreas funcionais e necessidades específicas de
            reorganização:
          </p>

          <ul>
            <li>
              Piso -1: mercado de produtores, áreas técnicas,
              armazenamento e logística.
            </li>

            <li>
              Piso 0: área principal de mercado e espaços
              comerciais.
            </li>

            <li>
              Piso 1: lojas e serviços atualmente com baixa
              atratividade e utilização reduzida.
            </li>
          </ul>


          <h3>
            Objetivos da intervenção
          </h3>

          <ul>
            <li>
              Modernização das instalações e infraestruturas.
            </li>

            <li>
              Melhoria das condições térmicas, acústicas e
              acessibilidade.
            </li>

            <li>
              Reorganização funcional do equipamento.
            </li>

            <li>
              Valorização do mercado enquanto património municipal.
            </li>
          </ul>


          <h3>
            Relevância para o projeto
          </h3>

          <p>
            A intervenção apresenta elevada complexidade por atuar
            sobre uma construção existente, exigindo articulação
            entre arquitetura, especialidades e manutenção da
            atividade do equipamento.
          </p>


        </MostrarMais>

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
