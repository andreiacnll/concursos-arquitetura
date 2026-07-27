import {
  CheckCircle2,
  AlertTriangle,
  CircleHelp
} from "lucide-react";


type Props = {
  decisao:any;
};



function ScoreCircle({
  value
}:{
  value:number
}){


  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset =
    circumference - (value / 100) * circumference;


  return (

    <div className="score-wrapper">

      <svg width="110" height="110">

        <circle
          cx="55"
          cy="55"
          r={radius}
          stroke="#ecebe5"
          strokeWidth="8"
          fill="none"
        />


        <circle
          cx="55"
          cy="55"
          r={radius}
          stroke="#6d9360"
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 55 55)"
        />

      </svg>


      <div className="score-number">

        <strong>
          {value}
        </strong>

        <small>
          /100
        </small>

      </div>


    </div>

  );

}




function RiskGauge({
 nivel
}:{
 nivel:string
}){


 const value =
 nivel==="Baixo"
 ? 30
 : nivel==="Médio"
 ? 60
 : 90;


 const rotation = -90 + (value * 1.8);



 return (

  <div className="risk-gauge">


   <svg
    width="150"
    height="90"
    viewBox="0 0 150 90"
   >


    <path
     d="M25 75 A50 50 0 0 1 125 75"
     fill="none"
     stroke="#e8e8e2"
     strokeWidth="10"
     strokeLinecap="round"
    />


    <path
     d="M25 75 A50 50 0 0 1 125 75"
     fill="none"
     stroke="#6d9360"
     strokeWidth="10"
     strokeLinecap="round"
     strokeDasharray="157"
     strokeDashoffset={157 - (157 * value / 100)}
    />


    <line
     x1="75"
     y1="75"
     x2="75"
     y2="40"
     stroke="#222"
     strokeWidth="3"
     transform={`rotate(${rotation} 75 75)`}
    />


   </svg>


   <strong>
    {nivel}
   </strong>


  </div>

 );

}


export default function DecisionDashboard({
 decisao
}:Props){


 const score =
 decisao?.score?.valor ??
 decisao?.score ??
 0;


 const oportunidades =
 decisao?.oportunidades ??
 decisao?.pontos_fortes ??
 [];


 const risco =
 decisao?.risco?.nivel ??
 "Médio";



 return (

<section className="decision-dashboard">


<div className="decision-header">

<h2>
Vale a pena concorrer?
</h2>

<p>
A nossa análise rápida para apoiar a decisão do atelier.
</p>

</div>



<div className="decision-grid">



<div className="decision-column score-column">

<span>
Score global
</span>


<ScoreCircle value={score}/>


<strong>
{decisao?.classificacao}
</strong>


</div>





<div className="decision-column">


<span>
Porque interessa
</span>


<ul>

{oportunidades.map(
(item:string)=>(
<li key={item}>
<CheckCircle2 size={15}/>
{item}
</li>
)
)}

</ul>


</div>





<div className="decision-column">


<span>
Nível de elegibilidade
</span>


<h3>
{decisao?.elegibilidade?.estado || "Compatível"}
</h3>


<p>
{decisao?.elegibilidade?.motivos?.join(". ")}
</p>


</div>





<div className="decision-column">


<span>
Risco de participação
</span>


<RiskGauge nivel={risco}/>


<p>
Existem fatores que podem excluir a candidatura.
</p>


</div>




</div>


</section>

 );

}
