import GlobalNavbar from "./GlobalNavbar";

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <GlobalNavbar />
      <div className="public-layout">
        {children}
      </div>
    </>
  );
}
