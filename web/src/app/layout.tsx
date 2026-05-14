import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { cookies, headers } from "next/headers";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { Providers } from "./providers";
import {
  AUTO_LANGUAGE_COOKIE,
  MANUAL_LANGUAGE_COOKIE,
  detectLanguageFromRequestParts,
} from "@/lib/i18n/languages";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OJIK BMS",
  description: "Integrated BMS rhythm game management service",
  icons: {
    icon: "/ojikbms_logo.png",
    apple: "/ojikbms_logo.png",
  },
};

async function getInitialLanguage() {
  const cookieStore = await cookies();
  const headerStore = await headers();

  return detectLanguageFromRequestParts({
    manualCookie: cookieStore.get(MANUAL_LANGUAGE_COOKIE)?.value ?? null,
    autoCookie: cookieStore.get(AUTO_LANGUAGE_COOKIE)?.value ?? null,
    acceptLanguage: headerStore.get("accept-language"),
    country: headerStore.get("x-vercel-ip-country") ?? headerStore.get("cf-ipcountry"),
  });
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const initialLanguage = await getInitialLanguage();

  return (
    <html lang={initialLanguage} suppressHydrationWarning>
      <body className={inter.className}>
        <Providers initialLanguage={initialLanguage}>{children}</Providers>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
