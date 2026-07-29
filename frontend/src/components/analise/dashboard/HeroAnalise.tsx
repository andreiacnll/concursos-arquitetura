import {
  ArrowLeft,
  ExternalLink,
  CalendarDays,
  Building2,
  Hash,
} from "lucide-react";


type Props = {
  identificacao?: any;
  concurso?: any;
  concursoId?: string;
};




export default function HeroAnalise({
  identificacao,
  concurso,
  concursoId,
}: Props) {

  return (
    <section className="hero-analise">


      <button className="back-button">
        <ArrowLeft size={15}/>
        Voltar aos resultados
      </button>



      <p className="eyebrow">
        ANÁLISE AUTOMÁTICA DE CONCURSO
      </p>



      <h1>
        {
          identificacao?.titulo ||
          identificacao?.identificacao?.titulo ||
          "Concurso público"
        }
      </h1>



      <div className="hero-location">

        📍 {identificacao?.localizacao || identificacao?.local || "Local não disponível"}

      </div>



      <div className="tags">

        {
          identificacao?.tipo?.map(
            (tipo:string)=>(
              <span key={tipo}>
                {tipo}
              </span>
            )
          )
        }

      </div>




      <div className="hero-meta">


        <div>
          <Building2 size={16}/>
          <span>
             {identificacao?.entidade || concurso?.entidade || "Entidade não disponível"}
          </span>
        </div>


        <div>
          <CalendarDays size={16}/>
          <span>
            {concurso?.data || "Data não disponível"}
          </span>
        </div>


        <div>
          <Hash size={16}/>
          <span>
            {concursoId || "—"}
          </span>
        </div>



        <a
          className="base-button"
          href={identificacao?.url_base || concurso?.link || "#"}
        >
          Abrir no Base.gov
          <ExternalLink size={15}/>
        </a>


      </div>



    </section>
  );
}
