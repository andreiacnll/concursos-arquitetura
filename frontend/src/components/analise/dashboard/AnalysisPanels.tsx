type Props = {
  estrategia?: any;
  analise?: any;
  equipa?: any;
  decisao?: any;
  criterio_resumo?: string;
};


export default function AnalysisPanels({
  estrategia,
  analise,
  equipa,
  criterio_resumo,
}: Props) {


  const especialidades =
    analise?.especialidades?.lista ?? [];


  return (
    <section className="analysis-panels">


      <article className="analysis-card">


        <span className="card-label">
          Critérios de adjudicação
        </span>


        <p>
          A avaliação privilegia a componente técnica
          da proposta face ao preço.
        </p>


        <strong className="card-highlight">
          {criterio_resumo || "60% Qualidade · 40% Preço"}
        </strong>


      </article>



      <article className="analysis-card">


        <span className="card-label">
          Complexidade
        </span>


        <p>
          {analise?.analise?.motivos?.join(". ")
          ||
          "Projeto com elevada exigência técnica e coordenação multidisciplinar."}
        </p>


        <div className="complexity-badge">
          <strong>
            {analise?.analise?.complexidade || "Muito alta"}
          </strong>
        </div>


      </article>




      <article className="analysis-card">


        <span className="card-label">
          Equipa necessária
        </span>


        <p>
          {especialidades
            .slice(0,5)
            .join(" · ")
          }
        </p>


        <strong className="team-number">
          {equipa?.total || 21}
          <small>
            elementos identificados
          </small>
        </strong>


      </article>



    </section>
  );
}
