"use client";

import { useState } from "react";

export default function ExpandableText({
  children,
}: {
  children: React.ReactNode;
}) {

  const [aberto, setAberto] = useState(false);

  return (
    <div>

      <div className={aberto ? "" : "collapsed-text"}>
        {children}
      </div>

      <button
        className="expand-button"
        onClick={() => setAberto(!aberto)}
      >
        {aberto ? "Mostrar menos ↑" : "Mostrar mais ↓"}
      </button>

    </div>
  );
}
