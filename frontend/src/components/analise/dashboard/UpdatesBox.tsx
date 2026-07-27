"use client";

import { useState } from "react";
import { Bell, Bookmark } from "lucide-react";


export default function UpdatesBox(){

const [alertas,setAlertas] = useState(false);
const [favorito,setFavorito] = useState(false);


return (

<section className="updates-box">


<div className="updates-text">

<div className="updates-title">

<Bell size={20}/>

<h3>
Quer receber atualizações deste concurso?
</h3>

</div>


<p>
Receba avisos sobre esclarecimentos,
alterações, prazos e novidades importantes.
</p>


</div>



<div className="updates-actions">


<button
className={`favorite-button ${favorito ? "active":""}`}
onClick={()=>setFavorito(!favorito)}
>

<Bookmark size={17}/>

{favorito
? "Guardado"
: "Guardar favorito"
}

</button>



<button
className="alert-button"
onClick={()=>setAlertas(!alertas)}
>


<Bell size={17}/>

{alertas
? "Alertas ativos"
: "Ativar alertas"
}


</button>


</div>


</section>


);


}
