"use client";

import PrivateLayout from "@/components/layout/PrivateLayout";
import { ProfileProvider } from "@/context/ProfileContext";
import ProfileLayout from "@/components/perfil/ProfileLayout";

export default function PerfilPage() {
  return (
    <PrivateLayout>
      <ProfileProvider>
        <ProfileLayout />
      </ProfileProvider>
    </PrivateLayout>
  );
}
