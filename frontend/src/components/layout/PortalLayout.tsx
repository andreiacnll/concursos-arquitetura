import Sidebar from "./Sidebar";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {

  return (

    <div className="portal-layout">

      <Sidebar />

      <main className="portal-content">
        {children}
      </main>

    </div>

  );

}
