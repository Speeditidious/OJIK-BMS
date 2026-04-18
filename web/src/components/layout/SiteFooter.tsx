import Image from "next/image";
import Link from "next/link";
import { Github } from "lucide-react";

type FooterLink = {
  href: string;
  label: string;
  external?: boolean;
};

const footerLinks: FooterLink[] = [
  { href: "/support", label: "Support" },
  { href: "/rules", label: "Rules" },
  { href: "/legal", label: "Legal" },
  { href: "/contributors", label: "Contributors" },
  {
    href: "https://github.com/Speeditidious/OJIK-BMS",
    label: "GitHub",
    external: true,
  },
];

const currentYear = new Date().getFullYear();

export function SiteFooter() {
  return (
    <footer className="relative overflow-hidden border-t border-border/70 bg-card/65">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, hsl(var(--background) / 0), hsl(var(--primary) / 0.7), hsl(var(--background) / 0))",
        }}
      />

      <div className="container relative mx-auto px-4 py-10">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-lg">
            <Link href="/" className="inline-flex items-center gap-3">
              <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={36} height={36} />
              <div>
                <div className="text-lg font-semibold tracking-tight">OJIK BMS</div>
                <div className="text-body text-muted-foreground">BMS 유저들만을 위한 성과 관리 사이트 - beta</div>
              </div>
            </Link>
          </div>

          <nav aria-label="Footer" className="flex flex-wrap gap-3">
            {footerLinks.map((link) =>
              link.external ? (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background/80 px-4 py-2 text-body font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {link.label}
                  <Github className="h-4 w-4" />
                </a>
              ) : (
                <Link
                  key={link.label}
                  href={link.href}
                  className="inline-flex items-center justify-center rounded-full border border-border bg-background/80 px-4 py-2 text-body font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {link.label}
                </Link>
              )
            )}
          </nav>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between gap-2 border-t border-border/70 pt-5 text-label text-muted-foreground md:flex-row">
          <span>Beta service</span>
          <span>{`© ${currentYear} OJIK BMS`}</span>
        </div>
      </div>
    </footer>
  );
}
