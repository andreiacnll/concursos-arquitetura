type Props = {
  identificacao?: any;
};


export default function HeroAnalise({
  identificacao,
}: Props) {

  return (
    <section className="hero-analise">


      <p className="eyebrow">
        ANÁLISE AUTOMÁTICA DE CONCURSO
      </p>


      <h1>
        {identificacao?.titulo || identificacao?.identificacao?.titulo || 'Concurso público'}
      </h1>


      <p>
        📍 {identificacao.local}
      </p>


      <div className="tags">

        {identificacao.tipo?.map(
          (tipo: string) => (
            <span key={tipo}>
              {tipo}
            </span>
          )
        )}

      </div>


    </section>
  );
}
