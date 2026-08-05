"use client";

import { useState } from "react";
import { useProfile } from "@/context/ProfileContext";
import OnboardingStepType from "./OnboardingStepType";
import OnboardingStepAtelier from "./OnboardingStepAtelier";
import { X, ArrowRight, Check } from "lucide-react";

interface Props {
  onClose: () => void;
}

export default function OnboardingModal({ onClose }: Props) {
  const { profile, setProfile, completeOnboarding } = useProfile();
  const [step, setStep] = useState(0);
  const [userType, setUserType] = useState<string>(profile.userType ?? "");

  const totalSteps = userType === "atelier" ? 2 : 1;

  const handleNext = () => {
    if (step === 0) {
      setProfile({ ...profile, userType: userType as any });
      if (userType === "atelier") {
        setStep(1);
      } else {
        completeOnboarding();
        onClose();
      }
    } else {
      completeOnboarding();
      onClose();
    }
  };

  const canProceed = step === 0 ? userType !== "" : true;

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-modal">
        <button className="onboarding-close" onClick={onClose}>
          <X size={20} />
        </button>

        <div className="onboarding-progress">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`onboarding-dot ${i <= step ? "active" : ""}`}
            />
          ))}
        </div>

        {step === 0 && (
          <OnboardingStepType selected={userType} onSelect={setUserType} />
        )}

        {step === 1 && <OnboardingStepAtelier />}

        <div className="onboarding-actions">
          {step > 0 && (
            <button className="onboarding-btn secondary" onClick={() => setStep(step - 1)}>
              Anterior
            </button>
          )}
          <button
            className="onboarding-btn primary"
            disabled={!canProceed}
            onClick={handleNext}
          >
            {step === totalSteps - 1 ? (
              <>
                Concluir
                <Check size={18} />
              </>
            ) : (
              <>
                Continuar
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}