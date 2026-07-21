#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
APP_DIR="$FRONTEND_DIR/src/app"
COMPONENTS_DIR="$FRONTEND_DIR/src/components"
HISTORICO_DIR="$APP_DIR/historico"

if [ ! -d "$APP_DIR" ]; then
  echo "ERRO: não encontrei $APP_DIR"
  echo "Executa este script na raiz do projeto."
  exit 1
fi

mkdir -p "$HISTORICO_DIR"

echo "→ A criar página Histórico"

cat > "$HISTORICO_DIR/page.tsx" <<'TSX'
import Link from "next/link";
import { ArrowLeft, Archive, CalendarDays, ExternalLink } from "lucide-react";
import type { Concurso } from "@/components/competition-types";

async function getHistorico(): Promise<Concurso[]> {
  try {
    const response = await fetch(
      "http://127.0.0.1:8000/concursos?estado=encerrado&limite=100",
      { cache: "no-store" },
    );

    if (!response.ok) {
      throw new Error(`A API respondeu com o estado ${response.status}`);
    }

    const data = await response.json();

    if (Array.isArray(data)) return data;
    if (Array.isArray(data.resultados)) return data.resultados;

    return [];
  } catch (error) {
    console.error("Erro ao carregar histórico:", error);
    return [];
  }
}

function formatDate(value: string | null) {
  if (!value) return "Sem data";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("pt-PT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export default async function HistoricoPage() {
  const concursos = await getHistorico();

  return (
    <main className="history-page">
      <header className="history-header">
        <div className="site-container history-navbar">
          <Link href="/" className="history-back">
            <ArrowLeft size={18} />
            Voltar aos concursos
          </Link>

          <Link href="/" className="history-brand">
            ARQCONCURSOS
          </Link>
        </div>
      </header>

      <section className="site-container history-hero">
        <div>
          <p className="eyebrow">Arquivo</p>
          <h1>Histórico de concursos</h1>
          <p>
            Consulta concursos públicos de arquitetura cujo prazo já terminou.
          </p>
        </div>

        <div className="history-counter">
          <Archive size={24} />
          <div>
            <strong>{concursos.length}</strong>
            <span>concursos encerrados</span>
          </div>
        </div>
      </section>

      <section className="site-container history-list">
        {concursos.length > 0 ? (
          concursos.map((concurso) => (
            <article key={concurso.id} className="history-item">
              <div className="history-item-main">
                <p className="history-entity">{concurso.entidade}</p>
                <h2>{concurso.titulo}</h2>

                <div className="history-meta">
                  <span>
                    <CalendarDays size={15} />
                    Publicado em {formatDate(concurso.data)}
                  </span>

                  <span>
                    <CalendarDays size={15} />
                    Prazo: {formatDate(concurso.data_limite)}
                  </span>
                </div>
              </div>

              <div className="history-item-side">
                <span className="history-status">Encerrado</span>

                {concurso.preco_base && (
                  <strong className="history-value">{concurso.preco_base}</strong>
                )}

                <a
                  href={concurso.link}
                  target="_blank"
                  rel="noreferrer"
                  className="history-link"
                >
                  Ver anúncio
                  <ExternalLink size={15} />
                </a>
              </div>
            </article>
          ))
        ) : (
          <div className="history-empty">
            <Archive size={32} />
            <h2>Ainda não existem concursos no histórico</h2>
            <p>
              Quando existirem concursos encerrados, irão aparecer nesta página.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
TSX

echo "→ A adicionar estilos"

cat >> "$APP_DIR/globals.css" <<'CSS'

/* Histórico */

.history-page {
  min-height: 100vh;
  background: var(--background);
}

.history-header {
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.88);
}

.history-navbar {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-back,
.history-brand,
.history-link {
  color: var(--foreground);
  text-decoration: none;
}

.history-back {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
}

.history-back:hover,
.history-link:hover {
  color: var(--accent);
}

.history-brand {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.22em;
}

.history-hero {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 48px;
  padding-top: 60px;
  padding-bottom: 60px;
}

.history-hero h1 {
  margin: 16px 0 14px;
  font-size: clamp(44px, 5vw, 72px);
  line-height: 1;
  font-weight: 520;
  letter-spacing: -0.05em;
}

.history-hero > div > p:last-child {
  max-width: 590px;
  margin: 0;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.6;
}

.history-counter {
  min-width: 230px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
  box-shadow: var(--shadow);
}

.history-counter div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-counter strong {
  font-size: 28px;
  font-weight: 520;
}

.history-counter span {
  color: var(--muted);
  font-size: 12px;
}

.history-list {
  padding-bottom: 90px;
}

.history-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 32px;
  padding: 30px 0;
  border-top: 1px solid var(--line);
}

.history-item:last-child {
  border-bottom: 1px solid var(--line);
}

.history-entity {
  margin: 0 0 10px;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  font-weight: 700;
}

.history-item h2 {
  max-width: 900px;
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 520;
  letter-spacing: -0.025em;
}

.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 18px;
  color: var(--muted);
  font-size: 12px;
}

.history-meta span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.history-item-side {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
}

.history-status {
  padding: 6px 10px;
  border-radius: 999px;
  background: #ededeb;
  color: #5d6063;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 10px;
  font-weight: 700;
}

.history-value {
  font-size: 14px;
  font-weight: 520;
}

.history-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 600;
}

.history-empty {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  text-align: center;
  color: var(--muted);
  border-top: 1px solid var(--line);
}

.history-empty h2 {
  margin: 18px 0 6px;
  color: var(--foreground);
  font-size: 24px;
}

.history-empty p {
  margin: 0;
}

@media (max-width: 760px) {
  .history-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-counter {
    width: 100%;
  }

  .history-item {
    grid-template-columns: 1fr;
  }

  .history-item-side {
    align-items: flex-start;
  }
}
CSS

echo "→ A atualizar o link da navbar"

python3 - <<'PY'
from pathlib import Path

path = Path("frontend/src/components/Navbar.tsx")
text = path.read_text(encoding="utf-8")

old = '''          <Link href="#concursos">Concursos</Link>
          <Link href="#sobre">Sobre</Link>'''

new = '''          <Link href="#concursos">Concursos</Link>
          <Link href="/historico">Histórico</Link>
          <Link href="#sobre">Sobre</Link>'''

if old in text:
    text = text.replace(old, new)
elif 'href="/historico"' not in text:
    print("AVISO: não consegui inserir automaticamente o link Histórico.")
else:
    print("O link Histórico já existe.")

path.write_text(text, encoding="utf-8")
PY

echo ""
echo "✓ Página Histórico criada."
echo "✓ Rota disponível em: http://localhost:3000/historico"
echo ""
echo "Se o servidor já estiver ativo, basta atualizar o navegador."
