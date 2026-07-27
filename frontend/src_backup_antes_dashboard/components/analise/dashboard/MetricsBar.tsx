type Props = {
  investimento: any;
  programa: any;
};


export default function MetricsBar({
  investimento,
  programa,
}: Props) {

  return (

    <section className="metrics-bar">


      <div className="metric-item">

        <span>
          Valor do contrato
        </span>

        <strong>
          {investimento?.valor_obra || '8.600.000 €'}
        </strong>

        <small>
          Sem IVA
        </small>

      </div>



      <div className="metric-item">

        <span>
          Área de intervenção
        </span>

        <strong>
          {programa.areas.total}
        </strong>

      </div>



      <div className="metric-item">

        <span>
          Prazo de entrega
        </span>

        <strong>
          {investimento.prazo_projeto}
        </strong>

        <small>
          Prazo previsto
        </small>

      </div>



      <div className="metric-item">

        <span>
          Critério de adjudicação
        </span>

        <strong>
          70% Qualidade
        </strong>

        <small>
          30% Preço
        </small>


        <div className="criteria-line">

          <div className="criteria-quality"></div>

          <div className="criteria-price"></div>

        </div>


      </div>



      <div className="metric-item">

        <span>
          Tipo de procedimento
        </span>

        <strong>
          Concurso público
        </strong>

        <small>
          Por prévia qualificação
        </small>

      </div>


    </section>

  );

}
