import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

function getSafeRedirectPath(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const redirectPath = getSafeRedirectPath(
    request.nextUrl.searchParams.get("next"),
  );

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      return NextResponse.redirect(new URL(redirectPath, request.url));
    }
  }

  const loginUrl = new URL("/auth/login", request.url);
  loginUrl.searchParams.set("error", "confirmation_failed");
  return NextResponse.redirect(loginUrl);
}
