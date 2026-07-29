import GlobalNavbar from "./GlobalNavbar";
import Sidebar from "./Sidebar";
import AuthGuard from "@/components/auth/AuthGuard";

export default function PrivateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <GlobalNavbar />
      <div className="private-layout">
        <Sidebar />
        <main className="private-content">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
