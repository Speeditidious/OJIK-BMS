import Link from "next/link";
import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

const supportSections = [
  {
    title: "현재 운영 상태",
    body: "베타 테스트 진행중입니다. 실무 경험 없는 초짜가 AI 뜌따이 해서 개발 중인거라 다소 이상한 동작이 많을 수 있습니다.",
  },
  {
    title: "후원 관련 안내",
    body: "지금은 별도의 후원 수단을 열어두지 않았습니다. 다만, 도메인 및 가상서버 비용이 지속적으로 발생하는 중이라 필요시 생길 수 있습니다.",
  },
  {
    title: "버그 제보 및 제안",
    body: "버그 제보, 기능 제안 등 모두 큰 도움이 됩니다. 현재 OJIK BMS 전용 디스코드 서버는 따로 운영하고 있지 않아서 Contributors의 개발자 디스코드 아이디 확인하셔서 DM 주시면 감사하겠습니다.",
  },
] as const;

export default function SupportPage() {
  return (
    <PublicInfoPageShell
      title="개발자 지원"
      description=""
    >
      {supportSections.map((section) => (
        <section
          key={section.title}
          className="border-t border-border/70 pt-6 first:border-t-0 first:pt-0"
        >
          <h2 className="text-xl font-semibold tracking-tight">{section.title}</h2>
          <p className="mt-3 text-body leading-relaxed text-muted-foreground">{section.body}</p>
        </section>
      ))}
    </PublicInfoPageShell>
  );
}
