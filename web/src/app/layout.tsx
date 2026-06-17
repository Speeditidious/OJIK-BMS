import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { DEFAULT_LANGUAGE } from "@/lib/i18n/languages";

const inter = Inter({ subsets: ["latin"] });

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
        <Providers initialLanguage={DEFAULT_LANGUAGE}>{children}</Providers>
      </body>
    </html>
  );
}
