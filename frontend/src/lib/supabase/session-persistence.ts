import type { CookieOptions } from "@supabase/ssr";

export const SESSION_PERSISTENCE_COOKIE = "cnll-remember-session";

const SESSION_PERSISTENCE_STORAGE_KEY = "cnll-remember-session";
const PERSISTENT_COOKIE_MAX_AGE = 400 * 24 * 60 * 60;

export function getSessionCookieOptions(
  options: CookieOptions,
  persistent: boolean,
) {
  if (persistent || options.maxAge === 0) {
    return options;
  }

  const sessionOptions = { ...options };
  delete sessionOptions.expires;
  delete sessionOptions.maxAge;
  return sessionOptions;
}

export function shouldPersistBrowserSession() {
  if (typeof window === "undefined") {
    return false;
  }

  return (
    window.localStorage.getItem(SESSION_PERSISTENCE_STORAGE_KEY) === "true"
  );
}

export function setBrowserSessionPersistence(persistent: boolean) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    SESSION_PERSISTENCE_STORAGE_KEY,
    String(persistent),
  );

  if (persistent) {
    document.cookie = `${SESSION_PERSISTENCE_COOKIE}=1; Path=/; SameSite=Lax; Max-Age=${PERSISTENT_COOKIE_MAX_AGE}`;
  } else {
    document.cookie = `${SESSION_PERSISTENCE_COOKIE}=; Path=/; SameSite=Lax; Max-Age=0`;
  }
}

export function clearBrowserSessionPersistence() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(SESSION_PERSISTENCE_STORAGE_KEY);
  document.cookie = `${SESSION_PERSISTENCE_COOKIE}=; Path=/; SameSite=Lax; Max-Age=0`;
}
