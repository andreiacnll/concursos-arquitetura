type Props = {
  investimento?: any;
  programa?: any;
  economia?: any;
  isConcursoConcecao?: boolean;
};


export default function MetricsBar({
  investimento,
  programa,
  economia,
  isConcursoConcecao = false,
}: Props) {

  // Para concursos de conceção: areas é um array de strings
  // Para concursos normais: areas é um objeto com chaves (ex: { total: "6990 m²" })
  const areaIntervencao = isConcursoConcecao
    ? (Array.isArray(programa?.areas) && programa.areas.length > 0
        ? programa.areas[0]
        : "Não indicada")
    : programa?.areas?.total;

  // Valor do contrato:
  // - Concursos normais: investimento.valor_obra
  // - Concursos de conceção: economia.valor_procedimento
  const valorContrato = isConcursoConcecao
    ? (economia?.valor_procedimento || "Não identificado")
    : (investimento?.valor_obra || "Não identificado");

  // Prazo de entrega:
  // - Concursos normais: investimento.prazo_projeto
  // - Concursos de conceção: não aplicável nesta fase
  const prazoEntrega = isConcursoConcecao
    ? "Não identificado"
    : (investimento?.prazo_projeto || "Não identificado");

  // Critério de adjudicação
  const criterioQualidade = isConcursoConcecao ? "Conceção" : "70% Qualidade";
  const criterioPreco = isConcursoConcecao ? "Por mérito" : "30% Preço";

  // Tipo de procedimento
  const tipoProcedimentoLabel = isConcursoConcecao
    ? "Concurso de conceção"
    : "Concurso público";
  const tipoProcedimentoSub = isConcursoConcecao
    ? "Por conceção"
    : "Por prévia qualificação";


  return (

    <section className="metrics-bar">


      <div className="metric-item">

        <span>
          {isConcursoConcecao ? "Valor do procedimento" : "Valor do contrato"}
        </span>

        <strong>
          {valorContrato}
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
          {areaIntervencao || "Não identificado"}
        </strong>

      </div>



      <div className="metric-item">

        <span>
          Prazo de entrega
        </span>

        <strong>
          {prazoEntrega}
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
          {criterioQualidade}
        </strong>

        <small>
          {criterioPreco}
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
          {tipoProcedimentoLabel}
        </strong>

        <small>
          {tipoProcedimentoSub}
        </small>

      </div>


    </section>

  );

}