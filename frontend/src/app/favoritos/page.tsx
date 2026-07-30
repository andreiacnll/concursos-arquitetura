"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PrivateLayout from "@/components/layout/PrivateLayout";
import { Heart, Star, Archive, ExternalLink } from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

type Favorito = {
  id: string;
  titulo: string;
  entidade: string;
  valor?: string;
  prazo?: string;
  score?: number;
  estado: "favorito" | "analisado" | "arquivado";
};

export default function FavoritosPage() {

  const [favoritos, setFavoritos] = useState<Favorito[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtro, setFiltro] = useState<string>("todos");

  useEffect(() => {
    fetch(`${API_URL}/favoritos`)
      .then(res => res.json())
      .then((dados: Favorito[]) => {
        setFavoritos(dados);
        setLoading(false);
      })
      .catch(() => {
        // Fallback: concursos conhecidos como exemplo
        setFavoritos([
          {
            id: "450837",
            titulo: "Requalificação do Mercado Municipal de Castelo Branco",
            entidade: "Município de Castelo Branco",
            valor: "8.600.000 €",
            prazo: "180 dias",
            score: 86,
            estado: "analisado",
          },
          {
            id: "420959",
            titulo: "Reabilitação da Escola Secundária do Lumiar",
            entidade: "Município de Lisboa",
            valor: "26.000 €",
            score: 85,
            estado: "analisado",
          },
        ]);
        setLoading(false);
      });
  }, []);

  const filtrados = filtro === "todos"
    ? favoritos
    : favoritos.filter(f => f.estado === filtro);

  return (
    <PrivateLayout>
      <main className="site-container" style={{ paddingTop: "32px" }}>

        <header style={{ marginBottom: "28px" }}>
          <h1 style={{ fontSize: "32px", fontWeight: 500, marginBottom: "8px" }}>
            <Heart size={28} style={{ marginRight: "10px", color: "#607b43" }} />
            Favoritos
          </h1>
          <p style={{ color: "#777", fontSize: "14px" }}>
            {favoritos.length} concurso{favoritos.length !== 1 ? "s" : ""} guardado{favoritos.length !== 1 ? "s" : ""}
          </p>
        </header>

        <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
          {["todos", "favorito", "analisado", "arquivado"].map((tipo) => (
            <button
              key={tipo}
              onClick={() => setFiltro(tipo)}
              style={{
                padding: "8px 18px",
                borderRadius: "10px",
                border: filtro === tipo ? "2px solid #607b43" : "1px solid #ddd",
                background: filtro === tipo ? "#f0f4ea" : "white",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: filtro === tipo ? 600 : 400,
                color: filtro === tipo ? "#607b43" : "#555",
              }}
            >
              {tipo === "todos" ? "Todos" : tipo === "favorito" ? "Favoritos" : tipo === "analisado" ? "Com análise" : "Arquivados"}
            </button>
          ))}
        </div>

        {loading ? (
          <p style={{ color: "#777", padding: "40px 0", textAlign: "center" }}>A carregar favoritos...</p>
        ) : filtrados.length === 0 ? (
          <div style={{
            textAlign: "center",
            padding: "60px 20px",
            background: "white",
            borderRadius: "18px",
            border: "1px solid #e8e8e2",
          }}>
            <Heart size={48} style={{ color: "#ddd", marginBottom: "16px" }} />
            <h3 style={{ fontWeight: 500, marginBottom: "8px" }}>Nenhum favorito</h3>
            <p style={{ color: "#777", fontSize: "14px" }}>
              Guarda concursos como favoritos para os acompanhares aqui.
            </p>
            <Link href="/entidades">
              <button style={{
                marginTop: "16px",
                padding: "10px 24px",
                background: "#111",
                color: "white",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
              }}>
                Explorar concursos
              </button>
            </Link>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {filtrados.map((fav) => (
              <div key={fav.id} style={{
                display: "flex",
                alignItems: "center",
                gap: "16px",
                padding: "20px 24px",
                background: "white",
                borderRadius: "16px",
                border: "1px solid #e8e8e2",
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <Star size={16} style={{ color: fav.estado === "analisado" ? "#607b43" : "#ccc" }} />
                    <h3 style={{ fontSize: "16px", fontWeight: 600, margin: 0 }}>{fav.titulo}</h3>
                  </div>
                  <p style={{ fontSize: "13px", color: "#777", margin: 0 }}>{fav.entidade}</p>
                  <div style={{ display: "flex", gap: "16px", marginTop: "8px", fontSize: "12px", color: "#999" }}>
                    {fav.valor && <span>💰 {fav.valor}</span>}
                    {fav.prazo && <span>📅 {fav.prazo}</span>}
                  </div>
                </div>

                {fav.score && (
                  <div style={{
                    textAlign: "center",
                    padding: "8px 16px",
                    background: "#f0f4ea",
                    borderRadius: "10px",
                  }}>
                    <div style={{ fontSize: "11px", color: "#777" }}>Score</div>
                    <strong style={{ fontSize: "20px", color: "#607b43" }}>{fav.score}</strong>
                  </div>
                )}

                <Link href={`/analise/${fav.id}`} style={{
                  padding: "10px 20px",
                  background: fav.estado === "analisado" ? "#111" : "white",
                  color: fav.estado === "analisado" ? "white" : "#111",
                  border: fav.estado === "analisado" ? "none" : "1px solid #ddd",
                  borderRadius: "10px",
                  textDecoration: "none",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}>
                  {fav.estado === "analisado" ? "Ver análise" : "Ver concurso"}
                  <ExternalLink size={14} />
                </Link>
              </div>
            ))}
          </div>
        )}

      </main>
    </PrivateLayout>
  );
}