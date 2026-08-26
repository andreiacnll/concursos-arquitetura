"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

export type UserType = "individual" | "atelier" | "empresa" | null;

export interface AtelierData {
  nome: string;
  logotipo: string;
  localizacao: string;
  website: string;
  email: string;
  descricao: string;
  numElementos: string;
  anoFundacao: string;
}

export interface TeamData {
  dimensao: string;
  areas: string[];
}

export interface SpecialtiesData {
  areas: string[];
}

export interface PreferencesData {
  distritos: string[];
  municipios: string[];
  ambito: string;
  procedimentos: string[];
  servicos: string[];
  escala: string;
  intervaloPreco: string;
  categorias: string[];
}

export interface ExperienceData {
  anosAtividade: string;
  numProjetos: string;
  projetosPublicos: string;
  concursosGanhos: string;
  escalaHabitual: string;
}

export interface ProfileData {
  onboardingComplete: boolean;
  userType: UserType;
  atelier: AtelierData;
  team: TeamData;
  specialties: SpecialtiesData;
  preferences: PreferencesData;
  experience: ExperienceData;
}

const defaultProfile: ProfileData = {
  onboardingComplete: false,
  userType: null,
  atelier: {
    nome: "",
    logotipo: "",
    localizacao: "",
    website: "",
    email: "",
    descricao: "",
    numElementos: "",
    anoFundacao: "",
  },
  team: {
    dimensao: "",
    areas: [],
  },
  specialties: {
    areas: [],
  },
  preferences: {
    distritos: [],
    municipios: [],
    ambito: "nacional",
    procedimentos: [],
    servicos: [],
    escala: "",
    intervaloPreco: "",
    categorias: [],
  },
  experience: {
    anosAtividade: "",
    numProjetos: "",
    projetosPublicos: "",
    concursosGanhos: "",
    escalaHabitual: "",
  },
};

interface ProfileContextType {
  profile: ProfileData;
  hydrated: boolean;
  isEditing: boolean;
  editingProfile: ProfileData;
  setProfile: (data: ProfileData) => void;
  updateAtelier: (data: Partial<AtelierData>) => void;
  updateTeam: (data: Partial<TeamData>) => void;
  updateSpecialties: (data: Partial<SpecialtiesData>) => void;
  updatePreferences: (data: Partial<PreferencesData>) => void;
  updateExperience: (data: Partial<ExperienceData>) => void;
  completeOnboarding: () => void;
  resetProfile: () => void;
  startEditing: () => void;
  saveChanges: () => void;
  cancelEditing: () => void;
  updateEditingAtelier: (data: Partial<AtelierData>) => void;
  updateEditingTeam: (data: Partial<TeamData>) => void;
  updateEditingSpecialties: (data: Partial<SpecialtiesData>) => void;
  updateEditingPreferences: (data: Partial<PreferencesData>) => void;
  updateEditingExperience: (data: Partial<ExperienceData>) => void;
}

interface EditingProfileContextType {
  profile: ProfileData;
  isEditing: boolean;
  editingProfile: ProfileData;
  startEditing: () => void;
  saveChanges: () => void;
  cancelEditing: () => void;
  updateAtelier: (data: Partial<AtelierData>) => void;
  updateTeam: (data: Partial<TeamData>) => void;
  updateSpecialties: (data: Partial<SpecialtiesData>) => void;
  updatePreferences: (data: Partial<PreferencesData>) => void;
  updateExperience: (data: Partial<ExperienceData>) => void;
}

declare global {
  namespace React {
    interface Context<T> {
      displayName?: string;
    }
  }
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<ProfileData>(defaultProfile);
  const [hydrated, setHydrated] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProfileData>(defaultProfile);

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("profile_data");
      if (stored) {
        const parsed = JSON.parse(stored);
        setProfile(parsed);
        setEditingProfile(parsed);
      }
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  // Persist to localStorage on change
  useEffect(() => {
    if (hydrated) {
      localStorage.setItem("profile_data", JSON.stringify(profile));
    }
  }, [profile, hydrated]);

  const updateAtelier = (data: Partial<AtelierData>) => {
    setProfile((prev) => ({
      ...prev,
      atelier: { ...prev.atelier, ...data },
    }));
  };

  const updateTeam = (data: Partial<TeamData>) => {
    setProfile((prev) => ({
      ...prev,
      team: { ...prev.team, ...data },
    }));
  };

  const updateSpecialties = (data: Partial<SpecialtiesData>) => {
    setProfile((prev) => ({
      ...prev,
      specialties: { ...prev.specialties, ...data },
    }));
  };

  const updatePreferences = (data: Partial<PreferencesData>) => {
    setProfile((prev) => ({
      ...prev,
      preferences: { ...prev.preferences, ...data },
    }));
  };

  const updateExperience = (data: Partial<ExperienceData>) => {
    setProfile((prev) => ({
      ...prev,
      experience: { ...prev.experience, ...data },
    }));
  };

  const completeOnboarding = () => {
    setProfile((prev) => ({ ...prev, onboardingComplete: true }));
  };

  const resetProfile = () => {
    setProfile(defaultProfile);
    setEditingProfile(defaultProfile);
  };

  const startEditing = () => {
    setEditingProfile(profile);
    setIsEditing(true);
  };

  const saveChanges = () => {
    setProfile(editingProfile);
    setIsEditing(false);
  };

  const cancelEditing = () => {
    setEditingProfile(profile);
    setIsEditing(false);
  };

  const updateEditingAtelier = (data: Partial<AtelierData>) => {
    setEditingProfile((prev) => ({
      ...prev,
      atelier: { ...prev.atelier, ...data },
    }));
  };

  const updateEditingTeam = (data: Partial<TeamData>) => {
    setEditingProfile((prev) => ({
      ...prev,
      team: { ...prev.team, ...data },
    }));
  };

  const updateEditingSpecialties = (data: Partial<SpecialtiesData>) => {
    setEditingProfile((prev) => ({
      ...prev,
      specialties: { ...prev.specialties, ...data },
    }));
  };

  const updateEditingPreferences = (data: Partial<PreferencesData>) => {
    setEditingProfile((prev) => ({
      ...prev,
      preferences: { ...prev.preferences, ...data },
    }));
  };

  const updateEditingExperience = (data: Partial<ExperienceData>) => {
    setEditingProfile((prev) => ({
      ...prev,
      experience: { ...prev.experience, ...data },
    }));
  };

  return (
    <ProfileContext.Provider
      value={{
        profile,
        hydrated,
        isEditing,
        setProfile,
        updateAtelier,
        updateTeam,
        updateSpecialties,
        updatePreferences,
        updateExperience,
        completeOnboarding,
        resetProfile,
        startEditing,
        saveChanges,
        cancelEditing,
        editingProfile,
        updateEditingAtelier,
        updateEditingTeam,
        updateEditingSpecialties,
        updateEditingPreferences,
        updateEditingExperience,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}

export function useEditingProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useEditingProfile must be used within ProfileProvider");

  return {
    profile: ctx.editingProfile,
    isEditing: ctx.isEditing,
    editingProfile: ctx.editingProfile,
    startEditing: ctx.startEditing,
    saveChanges: ctx.saveChanges,
    cancelEditing: ctx.cancelEditing,
    updateAtelier: ctx.updateEditingAtelier,
    updateTeam: ctx.updateEditingTeam,
    updateSpecialties: ctx.updateEditingSpecialties,
    updatePreferences: ctx.updateEditingPreferences,
    updateExperience: ctx.updateEditingExperience,
  };
}
