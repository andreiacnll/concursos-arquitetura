type Props={
alerta:any;
}


export default function AlertCard({alerta}:Props){

return (

<article className="alert-card">


<div className="alert-symbol">
△
</div>


<div className="alert-content">


<h3>
{alerta.titulo} • {alerta.zona}
</h3>


<div className="alert-data">

<span>
Tipo<br/>
<b>{alerta.tipo}</b>
</span>

<span>
Valor mínimo<br/>
<b>{alerta.valor}</b>
</span>

<span>
Prazo mínimo<br/>
<b>{alerta.prazo}</b>
</span>

<span>
Critério<br/>
<b>{alerta.criterio}</b>
</span>

<span>
Frequência<br/>
<b>{alerta.frequencia}</b>
</span>


</div>


</div>


<div className="switch">
{alerta.ativo ? "●" : "○"}
</div>


</article>

)

}
