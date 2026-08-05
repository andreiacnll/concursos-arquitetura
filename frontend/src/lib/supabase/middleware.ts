import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import {
  getSessionCookieOptions,
  SESSION_PERSISTENCE_COOKIE,
} from "./session-persistence";

const protectedRoutes = [
  "/perfil",
  "/favoritos",
  "/analises",
  "/alertas",
  "/empresa",
];

function isProtectedPath(pathname: string) {
  return protectedRoutes.some((route) =>
    pathname === route || pathname.startsWith(`${route}/`),
  );
}

function copySessionState(source: NextResponse, target: NextResponse) {
  source.cookies.getAll().forEach((cookie) => target.cookies.set(cookie));

  for (const header of ["cache-control", "expires", "pragma"]) {
    const value = source.headers.get(header);
    if (value) {
      target.headers.set(header, value);
    }
  }

  return target;
}

function redirectToLogin(
  request: NextRequest,
  sessionResponse?: NextResponse,
) {
  const url = request.nextUrl.clone();
  url.pathname = "/auth/login";
  url.searchParams.set("redirect", request.nextUrl.pathname);
  const response = NextResponse.redirect(url);
  return sessionResponse
    ? copySessionState(sessionResponse, response)
    : response;
}

export async function updateSession(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isProtected = isProtectedPath(pathname);
  const isGuestOnlyRoute =
    pathname === "/auth/login" || pathname === "/auth/register";
  const persistent =
    request.cookies.get(SESSION_PERSISTENCE_COOKIE)?.value === "1";
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!supabaseUrl || !supabaseKey) {
    if (isProtected) {
      return redirectToLogin(request);
    }
    return NextResponse.next({ request });
  }

  let supabaseResponse = NextResponse.next({ request });

  let supabase;
  try {
    supabase = createServerClient(
      supabaseUrl,
      supabaseKey,
      {
        cookies: {
          getAll() {
            return request.cookies.getAll();
          },
          setAll(cookiesToSet, headers) {
            cookiesToSet.forEach(({ name, value }) =>
              request.cookies.set(name, value),
            );
            supabaseResponse = NextResponse.next({ request });
            cookiesToSet.forEach(({ name, value, options }) =>
              supabaseResponse.cookies.set(
                name,
                value,
                getSessionCookieOptions(options, persistent),
              ),
            );
            Object.entries(headers).forEach(([name, value]) =>
              supabaseResponse.headers.set(name, value),
            );
          },
        },
      },
    );
  } catch {
    if (isProtected) {
      return redirectToLogin(request);
    }
    return supabaseResponse;
  }

  // Refresh session
  const user = await supabase.auth
    .getUser()
    .then(({ data }) => data.user)
    .catch(() => null);

  // Redirect unauthenticated users to login
  if (isProtected && !user) {
    return redirectToLogin(request, supabaseResponse);
  }

  // Redirect authenticated users away from auth pages
  if (isGuestOnlyRoute && user) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return copySessionState(
      supabaseResponse,
      NextResponse.redirect(url),
    );
  }

  return supabaseResponse;
}
