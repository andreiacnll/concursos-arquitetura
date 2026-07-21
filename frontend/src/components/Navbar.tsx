"use client";

import Link from "next/link";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

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
  const [theme, setTheme] = useState<Theme>("light");
  const [themeLoaded, setThemeLoaded] = useState(false);

  useEffect(() => {
    const storedTheme = window.localStorage.getItem(
      "arqconcursos-theme",
    ) as Theme | null;

    const systemPrefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;

    const initialTheme: Theme =
      storedTheme === "dark" || storedTheme === "light"
        ? storedTheme
        : systemPrefersDark
          ? "dark"
          : "light";

    setTheme(initialTheme);
    document.documentElement.dataset.theme = initialTheme;
    setThemeLoaded(true);
  }, []);

  function toggleTheme() {
    const nextTheme: Theme = theme === "dark" ? "light" : "dark";

    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("arqconcursos-theme", nextTheme);
  }

  const isDark = theme === "dark";

  return (
    <header className="site-header">
      <div className="site-container navbar">
        <Link href="/" className="brand" aria-label="Portal Concursos">
          <LogoMark />
          <span>PORTAL CONCURSOS</span>
        </Link>

        <nav className="desktop-nav" aria-label="Navegação principal">
          <Link href="/#concursos">Concursos</Link>
          <Link href="/historico">Histórico</Link>
          <Link href="/#sobre">Sobre</Link>
          <Link href="/#como-funciona">Como funciona</Link>
          <Link href="/#newsletter">Newsletter</Link>
        </nav>

        <div className="navbar-actions">
          <button
            className="icon-button theme-toggle"
            type="button"
            aria-label={
              isDark ? "Ativar modo claro" : "Ativar modo escuro"
            }
            aria-pressed={isDark}
            title={isDark ? "Modo claro" : "Modo escuro"}
            onClick={toggleTheme}
          >
            {themeLoaded && isDark ? (
              <Moon size={18} strokeWidth={1.8} />
            ) : (
              <Sun size={18} strokeWidth={1.8} />
            )}
          </button>

          <button className="primary-button small" type="button">
            Entrar
          </button>
        </div>
      </div>
    </header>
  );
}
