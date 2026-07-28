import GlobalNavbar from "./GlobalNavbar";
import Sidebar from "./Sidebar";

export default function PrivateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <GlobalNavbar />
      <div className="private-layout">
        <Sidebar />
        <main className="private-content">
          {children}
        </main>
      </div>
    </>
  );
}