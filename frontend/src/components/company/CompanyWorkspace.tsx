"use client";

import { useEffect, useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { API_URL } from "@/lib/api";
import CompanyProfileForm from "@/components/company/CompanyProfileForm";
import CompanyOnboardingModal from "@/components/company/CompanyOnboardingModal";
import { saveCompanyProfileWithDiagnostics } from "@/lib/company-profile-api";
import {
  CompanyBasicInfo,
  CompanyProfile,
  createEmptyCompanyProfile,
  isCompanyProfileEmpty,
  needsCompanyOnboarding,
  normalizeCompanyProfile,
} from "@/components/company/company-types";
import {
  buildCompanyOnboardingDraftKey,
  draftHasProgress,
  loadCompanyOnboardingDraft,
} from "@/components/company/company-onboarding-draft";

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

function companyLoadError(
  response: Response,
  resource: "empresa" | "perfil",
): string {
  if (response.status === 401) {
    return "A sessão da empresa terminou. Volta a iniciar sessão.";
  }

  if (response.status === 403) {
    return "Não tens autorização para consultar esta empresa.";
  }

  if (response.status >= 500) {
    return `O servidor não conseguiu carregar ${resource} da empresa (HTTP ${response.status}).`;
  }

  return `Não foi possível carregar ${resource} da empresa (HTTP ${response.status}).`;
}

function buildOnboardingCompletedKey(
  userId: string | null | undefined,
): string | null {
  return userId ? `company-onboarding-completed:user:${userId}` : null;
}

export default function CompanyWorkspace({ embedded = false }: { embedded?: boolean }) {
  const { session, user, loading: authLoading } = useAuth();
  const [company, setCompany] = useState<CompanyBasicInfo | null>(null);
  const [profile, setProfile] = useState<CompanyProfile>(
    createEmptyCompanyProfile(),
  );
  const [draftProfile, setDraftProfile] = useState<CompanyProfile>(
    createEmptyCompanyProfile(),
  );
  const [hasProfile, setHasProfile] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [hasDraft, setHasDraft] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(false);

  useEffect(() => {
    const token = session?.access_token;
    if (!token) {
      return;
    }

    let active = true;

    async function loadProfile() {
      setLoading(true);
      setError(null);
      setSuccess(null);

      try {
        const [companyResponse, profileResponse] = await Promise.all([
          fetch(`${API_URL}/company`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
          fetch(`${API_URL}/company/profile`, {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }),
        ]);

        if (!active) return;

        let nextCompany: CompanyBasicInfo | null = null;
        let nextProfile = createEmptyCompanyProfile();
        let nextHasProfile = false;
        let nextError: string | null = null;

        if (companyResponse.ok) {
          const companyData = (await safeReadJson(
            companyResponse,
          )) as Partial<CompanyBasicInfo> | null;
          if (companyData && typeof companyData === "object") {
            nextCompany = {
              id: typeof companyData.id === "number" ? companyData.id : null,
              name: String(companyData.name ?? ""),
              website: String(companyData.website ?? ""),
              owner_user_id: companyData.owner_user_id,
            };
          }
        } else if (companyResponse.status !== 404) {
          nextError = companyLoadError(companyResponse, "empresa");
        }

        if (profileResponse.ok) {
          const profileData = await safeReadJson(profileResponse);
          nextProfile = normalizeCompanyProfile(profileData);
          nextHasProfile = true;
        } else if (profileResponse.status === 404) {
          nextProfile = createEmptyCompanyProfile();
          nextHasProfile = false;
        } else {
          nextError =
            nextError ?? companyLoadError(profileResponse, "perfil");
          nextProfile = createEmptyCompanyProfile();
          nextHasProfile = false;
        }

        setCompany(nextCompany);
        setProfile(nextProfile);
        setDraftProfile(nextProfile);
        setHasProfile(nextHasProfile);
        setIsEditing(false);
        setError(nextError);

        const completedKey = buildOnboardingCompletedKey(user?.id ?? null);
        const completed =
          completedKey !== null &&
          window.localStorage.getItem(completedKey) === "1";
        setOnboardingCompleted(completed);
        const draftKey = buildCompanyOnboardingDraftKey(user?.id ?? null);
        const draft = loadCompanyOnboardingDraft(draftKey);
        const draftExists = draftHasProgress(draft);
        setHasDraft(draftExists && !completed);
        const shouldOpen =
          !nextError &&
          !completed &&
          (draftExists || needsCompanyOnboarding(nextProfile));
        setShowOnboarding(shouldOpen);
      } catch {
        if (!active) return;
        setCompany(null);
        setProfile(createEmptyCompanyProfile());
        setDraftProfile(createEmptyCompanyProfile());
        setHasProfile(false);
        setIsEditing(false);
        setShowOnboarding(false);
        setHasDraft(false);
        setOnboardingCompleted(false);
        setError("Não foi possível contactar o servidor da empresa.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadProfile();

    return () => {
      active = false;
    };
  }, [authLoading, session?.access_token, user?.id]);

  useEffect(() => {
    const draftKey = buildCompanyOnboardingDraftKey(user?.id ?? null);
    const completedKey = buildOnboardingCompletedKey(user?.id ?? null);
    const refreshDraftState = () => {
      const draft = loadCompanyOnboardingDraft(draftKey);
      const completed =
        completedKey !== null &&
        window.localStorage.getItem(completedKey) === "1";
      setOnboardingCompleted(completed);
      setHasDraft(draftHasProgress(draft) && !completed);
    };

    refreshDraftState();

    if (typeof window === "undefined") return undefined;

    const handleStorage = (event: StorageEvent) => {
      if (event.key === draftKey || event.key === null) {
        refreshDraftState();
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [user?.id]);

  function handleEdit() {
    setDraftProfile(profile);
    setIsEditing(true);
    setError(null);
    setSuccess(null);
  }

  function handleCancel() {
    setDraftProfile(profile);
    setIsEditing(false);
    setError(null);
    setSuccess(null);
  }

  function closeOnboarding() {
    setShowOnboarding(false);
  }

  function completeOnboarding() {
    const completedKey = buildOnboardingCompletedKey(user?.id ?? null);
    if (completedKey) {
      window.localStorage.setItem(completedKey, "1");
    }
    const draftKey = buildCompanyOnboardingDraftKey(user?.id ?? null);
    if (draftKey) {
      window.localStorage.removeItem(draftKey);
    }
    setHasDraft(false);
    setOnboardingCompleted(true);
    setShowOnboarding(false);
  }

  function openManualOnboarding() {
    setIsEditing(false);
    setError(null);
    setSuccess(null);
    setShowOnboarding(true);
  }

  async function handleSave() {
    const token = session?.access_token;
    if (!token) {
      setError("A sessão terminou. Volta a iniciar sessão.");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const saved = await saveCompanyProfileWithDiagnostics(
        token,
        draftProfile,
        hasProfile,
      );
      setProfile(saved);
      setDraftProfile(saved);
      setCompany((current) =>
        current
          ? {
              ...current,
              name: saved.identity.company_name || current.name,
              website: saved.identity.website || current.website,
            }
          : current,
      );
      setHasProfile(true);
      setIsEditing(false);
      setSuccess("Perfil da empresa guardado com sucesso.");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Não foi possível guardar o perfil da empresa.",
      );
    } finally {
      setSaving(false);
    }
  }

  const emptyProfile = isCompanyProfileEmpty(profile);

  return (
    <main
        className={embedded ? "company-workspace" : "site-container"}
        style={{
          paddingTop: "32px",
          paddingBottom: "56px",
          display: "grid",
          gap: "20px",
        }}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "16px",
            alignItems: "flex-start",
            flexWrap: "wrap",
          }}
        >
          <div>
            <p
              style={{
                margin: 0,
                fontSize: "12px",
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "#8a8a82",
              }}
            >
              Área da empresa
            </p>
            <h1 style={{ fontSize: "30px", margin: "6px 0 8px" }}>
              {company?.name || "Minha Empresa"}
            </h1>
            <p style={{ color: "#777", margin: 0 }}>
              Consulta e atualiza o perfil empresarial usado pelo backend de
              Company Intelligence.
            </p>
          </div>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            {(loading || authLoading) && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  color: "#607b43",
                }}
              >
                <Loader2 size={18} className="spin" />
                A carregar perfil...
              </div>
            )}
            {!loading && !authLoading && !error && (
              <button
                className={hasDraft && !onboardingCompleted ? "btn-primary" : "btn-secondary"}
                type="button"
                onClick={openManualOnboarding}
              >
                {hasDraft && !onboardingCompleted
                  ? "Continuar configuração da empresa"
                  : "Conhecer a empresa"}
              </button>
            )}
          </div>
        </header>

        {loading || authLoading ? (
          <section
            style={{
              background: "white",
              border: "1px solid #e7e7e0",
              borderRadius: "18px",
              padding: "32px",
              textAlign: "center",
            }}
          >
            <Loader2 size={28} className="spin" />
            <p style={{ color: "#777", marginTop: "14px" }}>
              A preparar a área da empresa...
            </p>
          </section>
        ) : error ? (
          <section
            style={{
              background: "white",
              border: "1px solid #e7e7e0",
              borderRadius: "18px",
              padding: "28px",
              textAlign: "center",
            }}
          >
            <p style={{ color: "#9f3a3a", marginBottom: "16px" }} role="alert">
              {error}
            </p>
            <div
              style={{
                display: "flex",
                gap: "12px",
                justifyContent: "center",
                flexWrap: "wrap",
              }}
            >
              <button
                className="btn-primary"
                type="button"
                onClick={() => window.location.reload()}
              >
                <RotateCcw size={16} />
                Recarregar
              </button>
              <button
                className="btn-secondary"
                type="button"
                onClick={openManualOnboarding}
              >
                Abrir onboarding
              </button>
            </div>
          </section>
        ) : (
          <>
            {emptyProfile && !isEditing && (
              <section
                style={{
                  background: "#fafaf7",
                  border: "1px dashed #ddd",
                  borderRadius: "18px",
                  padding: "18px 20px",
                  color: "#666",
                }}
              >
                Ainda não existe um perfil empresarial completo. Podes criar ou
                completar o perfil abaixo.
              </section>
            )}

            {success && (
              <section
                style={{
                  background: "#f4faef",
                  border: "1px solid #dce8c9",
                  borderRadius: "18px",
                  padding: "16px 20px",
                  color: "#4f6f2d",
                }}
                role="status"
              >
                {success}
              </section>
            )}

            <CompanyProfileForm
              profile={draftProfile}
              isEditing={isEditing}
              isNewProfile={!hasProfile}
              saving={saving}
              loading={loading}
              error={null}
              success={null}
              onEdit={handleEdit}
              onCancel={handleCancel}
              onSave={handleSave}
              onChange={setDraftProfile}
            />
          </>
        )}

        <CompanyOnboardingModal
          open={showOnboarding}
          token={session?.access_token || ""}
          userId={user?.id ?? null}
          company={company}
          profile={profile}
          hasProfile={hasProfile}
          onCompanyUpdated={(nextCompany) => {
            setCompany(nextCompany);
          }}
          onProfileUpdated={(nextProfile) => {
            const normalized = normalizeCompanyProfile(nextProfile);
            setProfile(normalized);
            setDraftProfile(normalized);
          }}
          onComplete={(nextProfile, nextCompany) => {
            const normalized = normalizeCompanyProfile(nextProfile);
            setProfile(normalized);
            setDraftProfile(normalized);
            setCompany(nextCompany);
            setHasProfile(true);
            completeOnboarding();
            setSuccess("Onboarding empresarial concluído.");
          }}
          onClose={closeOnboarding}
        />
    </main>
  );
}
