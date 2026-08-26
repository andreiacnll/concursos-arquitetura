"use client";

import { useCallback, useEffect, useState } from "react";
import ProfileSidebar from "./ProfileSidebar";
import ProfileIdentity from "./ProfileIdentity";
import ProfileNotifications from "./ProfileNotifications";
import ProfileAccountSecurity from "./ProfileAccountSecurity";
import ProfileCompanyPreferences from "./ProfileCompanyPreferences";
import ProfileCompanySources from "./ProfileCompanySources";
import UserProfileHeader from "./UserProfileHeader";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import CompanyInformationSection from "@/components/company/CompanyInformationSection";
import CompanyKnowledgeSection from "@/components/company/CompanyKnowledgeSection";
import CompanyExperienceCards from "@/components/company/CompanyExperienceCards";
import {
  CompanyBasicInfo,
  CompanyProfile,
  createEmptyCompanyProfile,
  normalizeCompanyProfile,
} from "@/components/company/company-types";

type CompanyMember = {
  id: number;
  user_id: string;
  role: string;
  status: string;
};

function safeReadJson(response: Response): Promise<unknown> {
  return response.text().then((text) => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    try {
      return JSON.parse(trimmed);
    } catch {
      return null;
    }
  });
}

function ValuesCard({
  title,
  description,
  values,
}: {
  title: string;
  description: string;
  values: string[];
}) {
  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      <div className="profile-card-body">
        {values.length === 0 ? (
          <div className="profile-empty-message">Sem informação guardada.</div>
        ) : (
          <div className="profile-chip-group">
            {values.map((value) => (
              <span key={value} className="profile-chip active">
                {value}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CompanyTeamCard({
  members,
  profile,
}: {
  members: CompanyMember[];
  profile: CompanyProfile;
}) {
  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <div>
          <h2>Equipa</h2>
          <p>Membros e papéis associados à empresa.</p>
        </div>
      </div>
      <div className="profile-card-body">
        <div className="profile-field">
          <label>Número de elementos</label>
          <div className="profile-value">
            {members.length > 0 ? members.length : "Não definido"}
          </div>
        </div>
        {members.length > 0 && (
          <div className="profile-notif-list">
            {members.map((member) => (
              <div key={member.id} className="profile-notif-item">
                <div className="profile-notif-info">
                  <strong>{member.user_id}</strong>
                  <span>{member.role} · {member.status}</span>
                </div>
              </div>
            ))}
          </div>
        )}
        {profile.specializations.length > 0 && (
          <div className="profile-field" style={{ marginTop: 20 }}>
            <label>Especializações da equipa</label>
            <div className="profile-chip-group">
              {profile.specializations.map((item) => (
                <span key={item} className="profile-chip active">
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProfileLayout() {
  const { session, user } = useAuth();
  const [activeSection, setActiveSection] = useState("personal");
  const [company, setCompany] = useState<CompanyBasicInfo | null>(null);
  const [companyProfile, setCompanyProfile] = useState<CompanyProfile>(
    createEmptyCompanyProfile(),
  );
  const [companyIntelligence, setCompanyIntelligence] = useState<any>(null);
  const [hasCompanyProfile, setHasCompanyProfile] = useState(false);
  const [members, setMembers] = useState<CompanyMember[]>([]);

  const refreshCompanyProfile = useCallback(async () => {
    const token = session?.access_token;
    if (!token) return;

    const response = await fetch(`${API_URL}/company/profile`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (response.ok) {
      setCompanyProfile(normalizeCompanyProfile(await safeReadJson(response)));
      setHasCompanyProfile(true);
    }
  }, [session?.access_token]);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) return;

    let active = true;
    Promise.all([
      fetch(`${API_URL}/company`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      }),
      fetch(`${API_URL}/company/profile`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      }),
      fetch(`${API_URL}/company/intelligence`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      }),
      fetch(`${API_URL}/company/members`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      }),
    ])
      .then(async ([companyResponse, profileResponse, intelligenceResponse, membersResponse]) => {
        if (!active) return;

        if (companyResponse.ok) {
          const data = (await safeReadJson(companyResponse)) as CompanyBasicInfo | null;
          setCompany(data);
        }
        if (profileResponse.ok) {
          setCompanyProfile(normalizeCompanyProfile(await safeReadJson(profileResponse)));
          setHasCompanyProfile(true);
        }
        if (intelligenceResponse.ok) {
          setCompanyIntelligence(await safeReadJson(intelligenceResponse));
        }
        if (membersResponse.ok) {
          const data = (await safeReadJson(membersResponse)) as {
            members?: CompanyMember[];
          } | null;
          setMembers(Array.isArray(data?.members) ? data.members : []);
        }
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [session?.access_token]);

  const currentMember = members.find((member) => member.user_id === user?.id);
  const experienceProfile = {
    ...companyProfile,
    project_experience_summary: Array.isArray(
      companyIntelligence?.projects?.summary,
    )
      ? companyIntelligence.projects.summary
      : [],
    project_experience_counts:
      companyIntelligence?.projects?.counts_by_typology ?? {},
    project_counts_by_typology:
      companyIntelligence?.projects?.counts_by_typology ?? {},
  };
  const sectionComponents: Record<string, React.ReactNode> = {
    personal: <ProfileIdentity />,
    account: <ProfileAccountSecurity />,
    notifications: <ProfileNotifications />,
    "company-identity": (
      <CompanyInformationSection
        profile={companyProfile}
        isEditing={false}
        onChange={() => {}}
      />
    ),
    team: <CompanyTeamCard members={members} profile={companyProfile} />,
    services: (
      <ValuesCard
        title="Serviços"
        description="Serviços registados no perfil partilhado da empresa."
        values={companyProfile.services}
      />
    ),
    specialties: (
      <ValuesCard
        title="Especialidades"
        description="Especializações da empresa e da equipa."
        values={companyProfile.specializations}
      />
    ),
    experience: <CompanyExperienceCards profile={experienceProfile} />,
    preferences: (
      <ProfileCompanyPreferences
        profile={companyProfile}
        token={session?.access_token}
        hasProfile={hasCompanyProfile}
        onSaved={(profile) => {
          setCompanyProfile(profile);
          setHasCompanyProfile(true);
        }}
      />
    ),
    knowledge: <CompanyKnowledgeSection profile={companyProfile} />,
    sources: (
      <ProfileCompanySources
        token={session?.access_token}
        onChanged={refreshCompanyProfile}
      />
    ),
  };

  return (
    <div className="profile-page">
      <UserProfileHeader
        companyName={company?.name || companyProfile.identity.company_name}
        companyRole={currentMember?.role}
      />

      <div className="profile-layout">
        <ProfileSidebar
          active={activeSection}
          onSelect={setActiveSection}
          onboardingComplete
        />

        <main className="profile-content">
          {sectionComponents[activeSection] || <ProfileIdentity />}
        </main>
      </div>
    </div>
  );
}
