import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";
import { DEFAULT_LANGUAGE } from "@/lib/i18n/languages";

const inter = localFont({
  display: "swap",
  fallback: ["Arial", "sans-serif"],
  src: [
    {
      path: "../assets/fonts/inter/2c55a0e60120577a-s.2a48534a.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/9c72aa0f40e4eef8-s.18a48cbc.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/ad66f9afd8947f86-s.7a40eb73.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/5476f68d60460930-s.c995e352.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/2bbe8d2671613f1f-s.76dcb0b2.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/1bffadaabf893a1e-s.7cd81963.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../assets/fonts/inter/83afe278b6a6bb3c-s.p.3a6ba036.woff2",
      style: "normal",
      weight: "100 900",
    },
  ],
});

export const metadata: Metadata = {
  title: "OJIK BMS",
  description: "Integrated BMS rhythm game management service",
  icons: {
    icon: "/ojikbms_logo.png",
    apple: "/ojikbms_logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang={DEFAULT_LANGUAGE} suppressHydrationWarning>
      <body className={inter.className}>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "window.__OJIK_INITIAL_URL__={pathname:location.pathname,search:location.search,hash:location.hash};",
          }}
        />
        <Providers initialLanguage={DEFAULT_LANGUAGE}>{children}</Providers>
      </body>
    </html>
  );
}
