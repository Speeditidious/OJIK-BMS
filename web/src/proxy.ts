import { NextRequest, NextResponse } from "next/server";
import {
  AUTO_LANGUAGE_COOKIE,
  MANUAL_LANGUAGE_COOKIE,
  detectLanguageFromRequestParts,
} from "@/lib/i18n/languages";

/**
 * Public routes that don't require authentication.
 * All other app routes are protected (client-side guard via useAuth hook).
 */
const PUBLIC_PATHS = ["/", "/login", "/auth/callback", "/tables"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const response = NextResponse.next();
  const manualCookie = request.cookies.get(MANUAL_LANGUAGE_COOKIE)?.value ?? null;
  const autoCookie = request.cookies.get(AUTO_LANGUAGE_COOKIE)?.value ?? null;

  if (!manualCookie && !autoCookie) {
    const country =
      request.headers.get("x-vercel-ip-country") ??
      request.headers.get("cf-ipcountry");
    const language = detectLanguageFromRequestParts({
      manualCookie,
      autoCookie,
      acceptLanguage: request.headers.get("accept-language"),
      country,
    });

    response.cookies.set(AUTO_LANGUAGE_COOKIE, language, {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365,
    });
  }

  // Allow public paths and static assets
  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/")) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return response;
  }

  // For protected routes, rely on client-side useAuth hook.
  // Server-side auth check would require cookies instead of localStorage.
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
