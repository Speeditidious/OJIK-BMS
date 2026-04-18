import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

const keyContributors = [
  { role: "레이팅 시스템", name: "모과맛" },
] as const;

const betaTesters = ["모과맛", "서준", "laigus", "Beatnoob", "Kaiden"] as const;

export default function ContributorsPage() {
  return (
    <PublicInfoPageShell
      title="기여자"
      description="기여해주신 모든 분들께 감사합니다."
    >
      <section className="border-t border-border/70 pt-6 first:border-t-0 first:pt-0">
        <h2 className="text-xl font-semibold tracking-tight">개발자</h2>
        <div className="mt-5 space-y-3">
          <div className="flex items-center gap-2 text-base">
            <span className="text-muted-foreground">-</span>
            <span className="font-semibold">레드볼</span>
            <span className="text-muted-foreground">·</span>
            <span>Discord: RedBall#9777</span>
            <span className="text-muted-foreground">·</span>
            <a
              href="https://github.com/Speeditidious"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-foreground transition-colors"
            >
              GitHub: Speeditidious
            </a>
          </div>
        </div>
      </section>

      <section className="border-t border-border/70 pt-6">
        <h2 className="text-xl font-semibold tracking-tight">핵심 기여자</h2>
        <div className="mt-5 space-y-3">
          {keyContributors.map(({ role, name }) => (
            <div key={name} className="flex items-center gap-2 text-base">
              <span className="text-muted-foreground">-</span>
              <span>{role}:</span>
              <span className="font-semibold">{name}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border/70 pt-6">
        <h2 className="text-xl font-semibold tracking-tight">베타 테스터</h2>
        <div className="mt-5 flex flex-wrap gap-2">
          {betaTesters.map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded-full border border-border bg-card/80 px-4 py-1.5 text-base font-semibold"
            >
              {name}
            </span>
          ))}
        </div>
      </section>
    </PublicInfoPageShell>
  );
}
