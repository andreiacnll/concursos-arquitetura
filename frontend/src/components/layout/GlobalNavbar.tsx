"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Moon, Sun, Menu, X, LogOut, UserRound } from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { useAuth } from "@/context/AuthContext";

type Theme = "light" | "dark";

const navItems = [
  { nome: "Pesquisa", href: "/" },
  { nome: "Favoritos", href: "/favoritos" },
  { nome: "Análises", href: "/analises" },
  { nome: "Alertas", href: "/alertas" },
  { nome: "Perfil", href: "/perfil" },
];

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

export default function GlobalNavbar() {
  const [theme, setTheme] = useState<Theme>("light");
  const [themeLoaded, setThemeLoaded] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const userMenuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function toggleTheme() {
    const nextTheme: Theme = theme === "dark" ? "light" : "dark";

    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("arqconcursos-theme", nextTheme);
  }

  const isDark = theme === "dark";

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <header className="site-header">
      <div className="site-container navbar">
        <Link href="/" className="brand" aria-label="Portal Concursos">
          <LogoMark />
          <span>PORTAL CONCURSOS</span>
        </Link>

        <nav className="desktop-nav" aria-label="Navegação principal">
          {navItems.map((item) => (
            <Link
              key={item.nome}
              href={item.href}
              className={isActive(item.href) ? "active" : ""}
            >
              {item.nome}
            </Link>
          ))}
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

          {loading ? null : user ? (
            <div className="navbar-user" ref={userMenuRef}>
              <button
                className="navbar-user-button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
              >
                <UserRound size={18} />
                <span>
                  {user.user_metadata?.nome || user.email?.split("@")[0] || "Utilizador"}
                </span>
              </button>

              {userMenuOpen && (
                <div className="navbar-user-menu">
                  <Link href="/perfil" onClick={() => setUserMenuOpen(false)}>
                    <UserRound size={15} />
                    Perfil
                  </Link>
                  <button
                    onClick={async () => {
                      setUserMenuOpen(false);
                      await signOut();
                      router.push("/");
                    }}
                  >
                    <LogOut size={15} />
                    Sair
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link href="/auth/login" className="primary-button small">
              Entrar
            </Link>
          )}

          <button
            className="icon-button mobile-menu-toggle"
            type="button"
            aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="mobile-nav" aria-label="Navegação móvel">
          {navItems.map((item) => (
            <Link
              key={item.nome}
              href={item.href}
              className={isActive(item.href) ? "active" : ""}
            >
              {item.nome}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
