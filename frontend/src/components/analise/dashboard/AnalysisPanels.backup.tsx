type Props = {
  estrategia?: any;
  analise?: any;
  equipa?: any;
  decisao?: any;
};


export default function AnalysisPanels({
  estrategia,
  analise,
  equipa,
}: Props) {

  return (
    <section className="analysis-panels">


      <article className="analysis-card">

        <h3>
          Critérios de adjudicação
        </h3>

        <p>
          {estrategia?.resumo ??
            "Informação de avaliação do concurso."}
        </p>

        <strong>
          {estrategia?.pontos_decisivos?.slice(0, 2).join(" · ") ??
            "Critérios não identificados"}
        </strong>

      </article>



      <article className="analysis-card">

        <h3>
          Complexidade
        </h3>

        <p>
          {analise?.analise?.motivos?.join(". ") ??
            "Análise de complexidade não disponível."}
        </p>

        <strong>
          {analise?.analise?.complexidade ??
            "Não avaliada"}
        </strong>

      </article>



      <article className="analysis-card">

        <h3>
          Equipa necessária
        </h3>

        <p>
          {equipa?.principais?.join(" · ") ??
            "Equipa não identificada."}
        </p>

        <strong>
          {equipa?.total
            ? `${equipa.total} elementos identificados`
            : "Ver requisitos da equipa"}
        </strong>

      </article>


    </section>
  );
}
