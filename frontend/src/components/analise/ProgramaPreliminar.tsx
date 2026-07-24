"use client";

import { useState } from "react";

export default function ProgramaPreliminar({
  resumo,
  detalhe,
}: {
  resumo: string;
  detalhe?: string;
}) {

  const [aberto, setAberto] = useState(false);

  return (
    <section className="programa-box">

      <h2>
        Programa preliminar
      </h2>


      <p>
        {resumo}
      </p>


      {aberto && (
        <div className="programa-detalhe">
          {detalhe}
        </div>
      )}


      <button
        onClick={() => setAberto(!aberto)}
      >
        {aberto
          ? "Mostrar menos ↑"
          : "Mostrar mais ↓"
        }
      </button>

    </section>
  );
}
