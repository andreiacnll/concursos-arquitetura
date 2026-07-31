import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import {
  getSessionCookieOptions,
  SESSION_PERSISTENCE_COOKIE,
} from "./session-persistence";

export async function createClient() {
  const cookieStore = await cookies();
  const persistent =
    cookieStore.get(SESSION_PERSISTENCE_COOKIE)?.value === "1";
  const supabaseKey =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    supabaseKey!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(
                name,
                value,
                getSessionCookieOptions(options, persistent),
              ),
            );
          } catch {
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing sessions.
          }
        },
      },
    },
  );
}
