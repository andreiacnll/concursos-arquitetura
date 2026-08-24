"use client";

import PrivateLayout from "@/components/layout/PrivateLayout";
import { ProfileProvider } from "@/context/ProfileContext";
import ProfileLayout from "@/components/perfil/ProfileLayout";
import CompanyWorkspace from "@/components/company/CompanyWorkspace";

export default function PerfilPage() {
  return (
    <PrivateLayout>
      <ProfileProvider>
        <ProfileLayout />
        <div id="minha-empresa" style={{ scrollMarginTop: "96px" }}>
          <CompanyWorkspace />
        </div>
      </ProfileProvider>
    </PrivateLayout>
  );
}
