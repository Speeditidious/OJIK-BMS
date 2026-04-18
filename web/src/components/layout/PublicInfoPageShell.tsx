import type { ReactNode } from "react";
import { Navbar } from "@/components/layout/navbar";
import { SiteFooter } from "@/components/layout/SiteFooter";

type PublicInfoPageShellProps = {
  title: string;
  description: string;
  children: ReactNode;
};

export function PublicInfoPageShell({
  title,
  description,
  children,
}: PublicInfoPageShellProps) {
  return (
    <>
      <main className="min-h-screen bg-background">
        <Navbar />
        <section className="container mx-auto px-4 py-12 md:py-16">
          <div className="mx-auto max-w-4xl">
            <header className="border-b border-border/70 pb-6">
              <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
              <p className="mt-3 text-body leading-relaxed text-muted-foreground">
                {description}
              </p>
            </header>
            <div className="mt-8 space-y-10">{children}</div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
