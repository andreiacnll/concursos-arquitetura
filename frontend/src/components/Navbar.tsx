import Link from "next/link";
import { Sun } from "lucide-react";

function LogoMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 38 34"
      className="h-8 w-9"
      fill="none"
    >
      <path d="M4 29L15.5 4L25 29" stroke="currentColor" strokeWidth="2.2" />
      <path d="M27.5 18L33.5 29" stroke="currentColor" strokeWidth="2.2" />
    </svg>
  );
}

export default function Navbar() {
  return (
    <header className="site-header">
      <div className="site-container navbar">
        <Link href="/" className="brand" aria-label="ArqConcursos">
          <LogoMark />
          <span>ARQCONCURSOS</span>
        </Link>

        <nav className="desktop-nav" aria-label="Navegação principal">
          <Link href="#concursos">Concursos</Link>
          <Link href="/historico">Histórico</Link>
          <Link href="#sobre">Sobre</Link>
          <Link href="#como-funciona">Como funciona</Link>
          <Link href="#newsletter">Newsletter</Link>
        </nav>

        <div className="navbar-actions">
          <button className="icon-button" type="button" aria-label="Alterar tema">
            <Sun size={18} strokeWidth={1.8} />
          </button>
          <button className="primary-button small" type="button">
            Entrar
          </button>
        </div>
      </div>
    </header>
  );
}
