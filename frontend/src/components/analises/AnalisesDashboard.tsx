"use client";

import Link from "next/link";
import {
  Activity,
  Clock3,
  CheckCircle2,
  FileSearch,
  Building2,
  CircleDot
} from "lucide-react";
import "./analises.css";


export default function AnalisesDashboard(){

return (

<div className="analises-page">


<header className="analises-header">

<div>
<h1>
Análises <span>IA</span>
</h1>

<p>
Acompanha as análises dos concursos que selecionaste.
</p>

</div>


<button>
Explorar concursos
</button>

</header>



<section className="analises-stats">

<div>
<Activity size={26}/><strong>18</strong>
<p>Total de análises</p>
<span>Desde o início</span>
</div>

<div>
<FileSearch size={26}/><strong>2</strong>
<p>A gerar</p>
<span>Em processamento</span>
</div>

<div>
<Clock3 size={26}/><strong>1</strong>
<p>Em fila</p>
<span>A aguardar início</span>
</div>

<div>
<CheckCircle2 size={26}/><strong>15</strong>
<p>Concluídas</p>
<span>Disponíveis</span>
</div>

</section>



<section className="analises-card">

<h2>
A gerar
</h2>


<div className="analise-item">

<div>
<div className="analise-title">
<CheckCircle2 size={20}/>
<h3>
Requalificação do Mercado Municipal de Castelo Branco
</h3>
</div>

<p>
Município de Castelo Branco
</p>

</div>


<div className="progress">
<div></div>
<p>68%</p>
</div>


<Link href="/analise/450837">
Acompanhar
</Link>


</div>



<div className="analise-item">

<div>
<div className="analise-title">
<FileSearch size={20}/>
<h3>
Centro de Saúde de Valença
</h3>
</div>

<p>
Administração Regional de Saúde do Norte
</p>

</div>


<div className="progress">
<div style={{width:"31%"}}></div>
<p>31%</p>
</div>


<Link href="/analise/450837">
Acompanhar
</Link>


</div>


</section>



<section className="analises-card">

<h2>
Histórico de análises
</h2>


<div className="analise-item">

<div>

<div className="analise-title">

<CheckCircle2 size={20}/>

<h3>
Requalificação do Mercado Municipal de Castelo Branco
</h3>

</div>


<p>
Município de Castelo Branco
</p>

</div>



<div className="score-box">

<strong>
Score IA
</strong>

<br/>

86 / 100

</div>



<Link href="/analise/450837">
Ver análise
</Link>


</div>


</section>



</div>

);

}
