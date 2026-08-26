"use client";

import { useState } from "react";

type Props = {
  titulo:string;
  items?:string[];
  vazio?:string;
};

export default function AccordionSection({
  titulo,
  items=[],
  vazio="Informação disponível brevemente."
}:Props){

  const [aberto,setAberto] = useState(false);

  return (
    <div className="accordion-section">

      <button
        onClick={()=>setAberto(!aberto)}
      >
        <span>{titulo}</span>
        <span>{aberto ? "⌃" : "⌄"}</span>
      </button>


      {aberto && (
        <div className="accordion-content">

          {items.length > 0 ? (

            <ul>
              {items.map(item=>(
                <li key={item}>
                  {item}
                </li>
              ))}
            </ul>

          ):(
            <p>{vazio}</p>
          )}

        </div>
      )}

    </div>
  );
}
