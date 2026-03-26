import { NextRequest, NextResponse } from "next/server";

/**
 * Public routes that don't require authentication.
 * All other app routes are protected (client-side guard via useAuth hook).
 */
const PUBLIC_PATHS = ["/", "/login", "/auth/callback", "/tables"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths and static assets
  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/")) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // For protected routes, rely on client-side useAuth hook.
  // Server-side auth check would require cookies instead of localStorage.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
