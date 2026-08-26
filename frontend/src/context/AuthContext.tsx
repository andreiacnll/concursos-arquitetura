"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { createClient } from "@/lib/supabase/client";
import {
  clearBrowserSessionPersistence,
  setBrowserSessionPersistence,
} from "@/lib/supabase/session-persistence";
import type { User, Session } from "@supabase/supabase-js";

type SignInResult = {
  error: string | null;
  session: Session | null;
};

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: (
    email: string,
    password: string,
    rememberSession: boolean,
  ) => Promise<SignInResult>;
  signUp: (
    email: string,
    password: string,
    metadata?: { nome?: string },
  ) => Promise<{ error: string | null }>;
  signOut: () => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function missingSupabaseConfigMessage() {
  const missing = [];
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
    missing.push("NEXT_PUBLIC_SUPABASE_URL");
  }
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY &&
    !process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  ) {
    missing.push("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  }

  return missing.length > 0
    ? `Configuração Supabase em falta: ${missing.join(", ")}.`
    : null;
}

function classifySignInError(error: unknown) {
  const message =
    error instanceof Error ? error.message : String(error || "");
  const normalized = message.toLowerCase();

  if (!message || normalized.includes("failed to fetch") || normalized.includes("network")) {
    return `Erro de rede ao contactar o Supabase. Detalhe: ${
      message || "sem detalhe devolvido"
    }`;
  }

  if (
    normalized.includes("invalid login credentials") ||
    normalized.includes("invalid credentials")
  ) {
    return `Credenciais inválidas. Supabase: ${message}`;
  }

  if (
    normalized.includes("email not confirmed") ||
    normalized.includes("email_not_confirmed")
  ) {
    return `Email não confirmado. Supabase: ${message}`;
  }

  return message;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const configError = missingSupabaseConfigMessage();
    if (configError) {
      setSession(null);
      setUser(null);
      setLoading(false);
      return;
    }

    let supabase;
    try {
      supabase = createClient();
    } catch {
      setSession(null);
      setUser(null);
      setLoading(false);
      return;
    }

    let active = true;
    let initialSessionLoaded = false;

    // Subscribe before loading the initial session, but keep the provider in
    // loading state until getSession() has completed. Otherwise the initial
    // auth event can briefly expose user=null and AuthGuard can redirect a
    // valid session to /auth/login.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (!active) return;

      // Do not let a delayed INITIAL_SESSION event overwrite the session
      // already resolved by getSession().
      if (event === "INITIAL_SESSION" && initialSessionLoaded) return;

      setSession(session);
      setUser(session?.user ?? null);

      if (initialSessionLoaded) {
        setLoading(false);
      }
    });

    // Get initial session
    supabase.auth
      .getSession()
      .then(({ data: { session } }) => {
        if (!active) return;

        setSession(session);
        setUser(session?.user ?? null);
      })
      .catch(() => {
        if (!active) return;

        setSession(null);
        setUser(null);
      })
      .finally(() => {
        initialSessionLoaded = true;
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async (
    email: string,
    password: string,
    rememberSession: boolean,
  ) => {
    const configError = missingSupabaseConfigMessage();
    if (configError) {
      return { error: configError, session: null };
    }

    const supabase = createClient();
    setBrowserSessionPersistence(rememberSession);

    let result;
    try {
      result = await supabase.auth.signInWithPassword({
        email,
        password,
      });
    } catch (error) {
      return { error: classifySignInError(error), session: null };
    }

    const { data, error } = result;

    if (error) {
      return { error: classifySignInError(error), session: null };
    }

    if (!data.session) {
      return {
        error:
          "Login aceite pelo Supabase, mas nenhuma sessão foi devolvida. Verifica a configuração de Auth/cookies.",
        session: null,
      };
    }

    setSession(data.session);
    setUser(data.session.user);
    setLoading(false);

    return { error: null, session: data.session };
  };

  const signUp = async (
    email: string,
    password: string,
    metadata?: { nome?: string },
  ) => {
    const configError = missingSupabaseConfigMessage();
    if (configError) {
      return { error: configError };
    }

    const supabase = createClient();
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: metadata,
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    return { error: error?.message ?? null };
  };

  const signOut = async () => {
    const supabase = createClient();
    const { error } = await supabase.auth.signOut({ scope: "local" });

    clearBrowserSessionPersistence();
    setSession(null);
    setUser(null);

    return { error: error?.message ?? null };
  };

  return (
    <AuthContext.Provider
      value={{ user, session, loading, signIn, signUp, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
