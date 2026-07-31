import type { Metadata } from "next";
import type { CSSProperties } from "react";
import "./globals.css";
import AuthWrapper from "@/components/auth/AuthWrapper";

export const metadata: Metadata = {
  title: "ArqConcursos | Concursos públicos de arquitetura",
  description:
    "Encontra concursos públicos de arquitetura, urbanismo e paisagismo em Portugal.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt"
      style={
        {
          "--font-geist-sans": "Arial, Helvetica, sans-serif",
          "--font-geist-mono": "Courier New, monospace",
        } as CSSProperties
      }
    >
      <body>
        <AuthWrapper>{children}</AuthWrapper>
      </body>
    </html>
  );
}
