"use client";

import { useEffect, useState } from "react";
import ProfileSidebar from "./ProfileSidebar";
import ProfileIdentity from "./ProfileIdentity";
import ProfileTeam from "./ProfileTeam";
import ProfileSpecialties from "./ProfileSpecialties";
import ProfilePreferences from "./ProfilePreferences";
import ProfileExperience from "./ProfileExperience";
import ProfileNotifications from "./ProfileNotifications";
import OnboardingModal from "./OnboardingModal";
import { useProfile, useEditingProfile } from "@/context/ProfileContext";

const sectionComponents: Record<string, React.ReactNode> = {
  identity: <ProfileIdentity />,
  team: <ProfileTeam />,
  specialties: <ProfileSpecialties />,
  preferences: <ProfilePreferences />,
  experience: <ProfileExperience />,
  notifications: <ProfileNotifications />,
};

export default function ProfileLayout() {
  const { profile, hydrated } = useProfile();
  const { isEditing, startEditing, saveChanges, cancelEditing } = useEditingProfile();
  const [activeSection, setActiveSection] = useState("identity");
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    if (hydrated) {
      setShowOnboarding(!profile.onboardingComplete);
    }
  }, [hydrated, profile.onboardingComplete]);

  return (
    <div className="profile-page">
      {showOnboarding && (
        <OnboardingModal onClose={() => setShowOnboarding(false)} />
      )}

      <div className="profile-layout">
        <ProfileSidebar
          active={activeSection}
          onSelect={setActiveSection}
          onboardingComplete={profile.onboardingComplete}
        />

        <main className="profile-content">
          {isEditing && (
            <div className="profile-edit-bar">
              <button className="btn-primary" onClick={saveChanges}>
                Guardar alterações
              </button>
              <button className="btn-secondary" onClick={cancelEditing}>
                Cancelar
              </button>
            </div>
          )}

          {!isEditing && (
            <div className="profile-edit-bar">
              <button className="btn-primary" onClick={startEditing}>
                Editar perfil
              </button>
            </div>
          )}

          {sectionComponents[activeSection] || <ProfileIdentity />}
        </main>
      </div>
    </div>
  );
}
