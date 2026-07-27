"use client";

import AlertCard from "./AlertCard";
import "./alerts.css";
import AnaliseLayout from "@/components/layout/AnaliseLayout";


const alertas = [
{
 titulo:"Arquitetura",
 zona:"Lisboa + Porto",
 tipo:"Concursos públicos",
 valor:"> 250.000 €",
 prazo:"> 45 dias",
 criterio:"Qualidade > 50%",
 frequencia:"Semanal",
 ativo:true
},
{
 titulo:"Paisagismo e espaço público",
 zona:"Todos os distritos",
 tipo:"Todos os procedimentos",
 valor:"> 100.000 €",
 prazo:"> 30 dias",
 criterio:"Qualidade > 40%",
 frequencia:"Diária",
 ativo:true
},
{
 titulo:"Equipamentos públicos",
 zona:"Norte e Centro",
 tipo:"Concursos públicos",
 valor:"> 500.000 €",
 prazo:"> 60 dias",
 criterio:"Preço < 40%",
 frequencia:"Semanal",
 ativo:false
}
];


export default function AlertsDashboard(){


return (

<AnaliseLayout>

<main className="site-container">

<div className="alerts-page">


<header className="alerts-header">

<div>

<div className="alerts-icon">
🔔
</div>

<h1>
Alertas
</h1>

<p>
Recebe notificações apenas dos concursos que te interessam.
</p>

</div>


<button className="new-alert">
+ Novo alerta
</button>


</header>



<div className="alerts-layout">


<section className="alerts-main">


<nav className="alerts-tabs">
<span className="active">Todos</span>
<span>Ativos</span>
<span>Pausados</span>
<span>Disparados</span>
<span>Arquivados</span>
</nav>


<div className="alerts-list">

{
alertas.map((a,i)=>(

<AlertCard
key={i}
alerta={a}
/>

))
}


</div>


<section className="found-projects">

<h2>
Novos concursos encontrados pelos teus alertas
</h2>


<div className="empty-cards">

<div/>
<div/>
<div/>

</div>


</section>



</section>



<aside className="alerts-side">


<div className="summary-card">

<h3>
Resumo dos teus alertas
</h3>


<strong>5</strong>
<span>Alertas ativos</span>


<strong>23</strong>
<span>Concursos encontrados esta semana</span>


<strong>Hoje, 09:32</strong>
<span>Última notificação enviada</span>


</div>


<div className="help-card">

<h3>
Como funcionam os alertas?
</h3>

<p>
Criamos alertas à medida dos teus critérios.
Recebes uma notificação sempre que surgem concursos relevantes.
</p>

</div>


</aside>



</div>


</div>

</main>

</AnaliseLayout>

);

}
