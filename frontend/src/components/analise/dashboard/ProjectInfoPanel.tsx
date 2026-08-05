"use client";

import { useState } from "react";
import { FileText, Users, Scale, AlertTriangle, History } from "lucide-react";
import ProjectMap from "../mapa/ProjectMap";


type Props = {
  ficha: any;
};


export default function ProjectInfoPanel({
  ficha,
}: Props) {


  const [open, setOpen] = useState<string | null>(null);


  const toggle = (id:string) => {
    setOpen(open === id ? null : id);
  };


  const entregaveis = ficha?.entregaveis?.principais ?? [];
  const especialidades = ficha?.especialidades?.lista ?? [];
  const requisitos = ficha?.requisitos?.obrigatorios ?? [];
  const riscos = ficha?.requisitos?.riscos_participacao ?? [];


  const normalizarNumero = (valor: unknown) => {
    if (typeof valor === "number") return Number.isFinite(valor) ? valor : null;
    if (typeof valor === "string") {
      const numero = Number(valor.replace(",", "."));
      return Number.isFinite(numero) ? numero : null;
    }
    return null;
  };

  const latitude = normalizarNumero(ficha?.localizacao?.latitude);
  const longitude = normalizarNumero(ficha?.localizacao?.longitude);
  const nomeLocal =
    ficha?.localizacao?.morada ||
    ficha?.localizacao?.freguesia ||
    ficha?.localizacao?.municipio ||
    ficha?.localizacao?.cidade ||
    ficha?.identificacao?.localizacao ||
    ficha?.identificacao?.local ||
    "Localização oficial não identificada";
  const localGenerico = ["portugal", "lisboa"].includes(
    String(nomeLocal).trim().toLowerCase()
  );
  const temCoordenadas =
    latitude !== null &&
    longitude !== null &&
    latitude >= 32 &&
    latitude <= 42.5 &&
    longitude >= -32 &&
    longitude <= -6;


  const mapaUrl =
    temCoordenadas
      ? `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`
      : !localGenerico && nomeLocal
      ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
          nomeLocal
        )}`
      : null;



  return (

    <aside className="project-info-panel">


      <div className="sidebar-cards">

      <ExpandableCard
        id="entregaveis"
        icon={<FileText size={18}/>} 
        title="Entregáveis principais"
        description="Lista completa dos documentos e elementos a apresentar."
        count={`${entregaveis.length} entregáveis`}
        open={open}
        toggle={toggle}
        items={entregaveis}
      />


      <ExpandableCard
        id="especialidades"
        icon={<Users size={18}/>} 
        title="Especialidades e consultores"
        description="Todas as especialidades previstas no programa preliminar."
        count={`${especialidades.length} especialidades`}
        open={open}
        toggle={toggle}
        items={especialidades}
      />


      <ExpandableCard
        id="requisitos"
        icon={<Scale size={18}/>} 
        title="Requisitos de habilitação"
        description="Condições obrigatórias para participação."
        count={`${requisitos.length} requisitos`}
        open={open}
        toggle={toggle}
        items={requisitos}
      />


      <ExpandableCard
        id="riscos"
        icon={<AlertTriangle size={18}/>} 
        title="Riscos e oportunidades"
        description="Principais fatores identificados."
        count={`${riscos.length} alertas`}
        open={open}
        toggle={toggle}
        items={riscos}
      />



      </div>


      <section className="entity-history">

        <h3><History size={18}/> Histórico da entidade</h3>

        <p>
          Informação disponível brevemente
        </p>

      </section>




      <section className="project-summary">


        <h3>
          Sobre o projeto
        </h3>


        <p>
          {ficha?.descricao ||
          "Requalificação, revitalização e modernização do projeto. Intervenção em edifício existente com integração urbana, funcional e técnica."}
        </p>


        {temCoordenadas && (

          <ProjectMap
            latitude={latitude}
            longitude={longitude}
          />

        )}


        <span className="project-location">

          📍 {nomeLocal}

        </span>


        {mapaUrl && (
        <a
          className="map-button"
          href={mapaUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Ver localização ↗
        </a>
        )}






      </section>


    </aside>

  );

}





function ExpandableCard({
  id,
  icon,
  title,
  description,
  count,
  open,
  toggle,
  items,

}:any) {


  const isOpen = open === id;


  return (

    <article
      className={`info-card ${isOpen ? "active" : ""}`}
    >


      <button
        className="info-card-button"
        onClick={() => toggle(id)}
      >


        <div className="info-card-icon">
          {icon}
        </div>


        <div className="info-card-content">

          <h4>
            {title}
          </h4>

          <p>
            {description}
          </p>

        </div>


        <div className="info-card-count">

          <span>
            {count}
          </span>


          <b>
            {isOpen ? "⌃" : "›"}
          </b>


        </div>


      </button>


      {isOpen && (

        <div className="info-card-details">

          {items.map((item:string)=>(

            <div key={item}>
              ✓ {item}
            </div>

          ))}

        </div>

      )}


    </article>

  );

}
