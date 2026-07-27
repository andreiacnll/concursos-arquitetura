"use client";

import { useState } from "react";

export default function MostrarMais({
  children,
}: {
  children: React.ReactNode;
}) {
  const [aberto, setAberto] = useState(false);

  return (
    <div>
      <div className={aberto ? "program-open" : "program-closed"}>
        {children}
      </div>

      <button
        className="expand-button"
        onClick={() => setAberto(!aberto)}
      >
        {aberto ? "Fechar análise ↑" : "Ler análise do programa ↓"}
      </button>
    </div>
  );
}
