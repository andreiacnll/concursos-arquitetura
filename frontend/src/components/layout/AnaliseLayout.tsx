import Sidebar from "./Sidebar";

export default function AnaliseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="analise-layout">

      <Sidebar />

      <main className="analise-content">
        {children}
      </main>

    </div>
  );
}
