"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
        <span>A carregar...</span>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}