"use client";

import { useState } from "react";
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


  const latitude = ficha?.localizacao?.latitude;
  const longitude = ficha?.localizacao?.longitude;


  const mapaUrl =
    latitude && longitude
      ? `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
          ficha?.localizacao?.cidade || "Portugal"
        )}`;



  return (

    <aside className="project-info-panel">


      <ExpandableCard
        id="entregaveis"
        icon="📄"
        title="Entregáveis principais"
        description="Lista completa dos documentos e elementos a apresentar."
        count={`${entregaveis.length} entregáveis`}
        open={open}
        toggle={toggle}
        items={entregaveis}
      />


      <ExpandableCard
        id="especialidades"
        icon="👥"
        title="Especialidades e consultores"
        description="Todas as especialidades previstas no programa preliminar."
        count={`${especialidades.length} especialidades`}
        open={open}
        toggle={toggle}
        items={especialidades}
      />


      <ExpandableCard
        id="requisitos"
        icon="⚖"
        title="Requisitos de habilitação"
        description="Condições obrigatórias para participação."
        count={`${requisitos.length} requisitos`}
        open={open}
        toggle={toggle}
        items={requisitos}
      />


      <ExpandableCard
        id="riscos"
        icon="⚠"
        title="Riscos e oportunidades"
        description="Principais fatores identificados."
        count={`${riscos.length} alertas`}
        open={open}
        toggle={toggle}
        items={riscos}
      />



      <section className="entity-history">

        <h3>
          Histórico da entidade
        </h3>

        <p>
          Informação disponível brevemente
        </p>

      </section>




      <section className="project-summary">


        <h3>
          Sobre o projeto
        </h3>


        <p>
          Requalificação, revitalização e modernização do projeto.
          Intervenção em edifício existente com integração urbana,
          funcional e técnica.
        </p>


        <strong>
          📍 {ficha?.localizacao?.morada || "Localização não disponível"}
        </strong>


        <span>
          {ficha?.localizacao?.cidade}
        </span>



        {latitude && longitude && (

          <ProjectMap
            latitude={latitude}
            longitude={longitude}
          />

        )}



        <a
          href={mapaUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="map-button"
        >
          Ver localização ↗
        </a>


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
