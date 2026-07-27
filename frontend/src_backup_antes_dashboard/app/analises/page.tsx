import Link from "next/link";

export default function AnalisesPage() {
  return (
    <main className="site-container">

      <section className="page-header">
        <p className="eyebrow">
          CONCURSOS ANALISADOS
        </p>

        <h1>
          Análises de concursos
        </h1>

        <p>
          Informação técnica extraída automaticamente
          das peças dos procedimentos.
        </p>
      </section>


      <section
        style={{
          marginTop: "40px",
          maxWidth: "420px",
        }}
      >

        <article
          style={{
            border: "1px solid #e5e5e5",
            borderRadius: "20px",
            padding: "28px",
            background: "#fff",
          }}
        >

          <span>
            🏛 Reabilitação
          </span>


          <h2
            style={{
              marginTop: "16px",
            }}
          >
            Restruturação, Revitalização e
            Modernização do Mercado Municipal
            de Castelo Branco
          </h2>


          <p>
            📍 Castelo Branco
          </p>


          <p>
            💰 Valor base: 300.000 €
          </p>


          <p>
            📄 Concurso público
          </p>


          <hr />


          <div>

            <strong>
              🤖 Análise automática disponível
            </strong>


            <p>
              Complexidade:
              {" "}
              <b>
                Muito alta
              </b>
            </p>


            <p>
              📚 26 documentos analisados
            </p>


            <p>
              ✅ Programa preliminar
              <br />
              ✅ Levantamento
              <br />
              ✅ Peças desenhadas
            </p>

          </div>


          <Link
            href="/analise/450837"
            style={{
              display: "inline-block",
              marginTop: "20px",
              fontWeight: 600,
            }}
          >
            Abrir análise →
          </Link>


        </article>

      </section>


    </main>
  );
}