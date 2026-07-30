"use client";

import { useEffect, useState } from "react";
import { Bell, Bookmark } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";


type Props = {
concursoId: number;
};


export default function UpdatesBox({ concursoId }: Props){

const { session } = useAuth();
const [alertas,setAlertas] = useState(false);
const [favorito,setFavorito] = useState(false);
const [loading,setLoading] = useState(false);
const [erro,setErro] = useState<string | null>(null);

useEffect(() => {
const token = session?.access_token;
if (!token || !concursoId) return;

fetch(`${API_URL}/alertas/${concursoId}/subscricao`, {
headers: { Authorization: `Bearer ${token}` },
})
.then(async (resposta) => {
if (!resposta.ok) return null;
return resposta.json();
})
.then((dados) => {
if (!dados) return;
setAlertas(Boolean(dados.ativo));
setFavorito(Boolean(dados.e_favorito));
});
}, [session?.access_token, concursoId]);

async function alternarFavorito(){
const token = session?.access_token;
if (!token || loading) return;

setLoading(true);
setErro(null);

try {
const resposta = await fetch(`${API_URL}/favoritos/${concursoId}`, {
method: favorito ? "DELETE" : "POST",
headers: { Authorization: `Bearer ${token}` },
});

if (!resposta.ok) {
throw new Error("Não foi possível atualizar o favorito.");
}

setFavorito(!favorito);
if (!favorito) {
setAlertas(true);
}
} catch (error) {
setErro(error instanceof Error ? error.message : "Não foi possível atualizar.");
} finally {
setLoading(false);
}
}

async function alternarAlertas(){
const token = session?.access_token;
if (!token || loading) return;

setLoading(true);
setErro(null);

try {
const resposta = await fetch(
`${API_URL}/alertas/${concursoId}/${alertas ? "desativar" : "ativar"}`,
{
method: alertas ? "DELETE" : "POST",
headers: { Authorization: `Bearer ${token}` },
},
);

if (!resposta.ok) {
throw new Error("Não foi possível atualizar os alertas.");
}

setAlertas(!alertas);
} catch (error) {
setErro(error instanceof Error ? error.message : "Não foi possível atualizar.");
} finally {
setLoading(false);
}
}


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
onClick={alternarFavorito}
disabled={loading}
>

<Bookmark size={17}/>

{favorito
? "Guardado"
: "Guardar favorito"
}

</button>



<button
className={`alert-button ${alertas ? "active":""}`}
onClick={alternarAlertas}
disabled={loading}
>


<Bell size={17}/>

{alertas
? "Alertas ativos"
: "Ativar alertas"
}


</button>


</div>

{erro && (
<p className="updates-error" role="alert">
{erro}
</p>
)}


</section>


);


}
