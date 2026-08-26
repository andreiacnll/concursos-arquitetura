"use client";

import { useState } from "react";
import ProfileSidebar from "./ProfileSidebar";
import ProfileIdentity from "./ProfileIdentity";
import ProfileAccountSecurity from "./ProfileAccountSecurity";
import UserProfileHeader from "./UserProfileHeader";
import CompanyWorkspace from "@/components/company/CompanyWorkspace";

export default function ProfileLayout() {
  const [activeSection, setActiveSection] = useState("profile");

  return (
    <div className="profile-page">
      <UserProfileHeader companyName={undefined} companyRole={undefined} />

      <div className="profile-layout">
        <ProfileSidebar active={activeSection} onSelect={setActiveSection} />

        <main className="profile-content">
          {activeSection === "company" ? (
            <div id="minha-empresa" style={{ scrollMarginTop: "96px" }}>
              <CompanyWorkspace embedded />
            </div>
          ) : (
            <>
              <ProfileIdentity />
              <ProfileAccountSecurity />
            </>
          )}
        </main>
      </div>
    </div>
  );
}