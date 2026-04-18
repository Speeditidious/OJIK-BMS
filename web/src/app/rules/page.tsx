import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

const rulesSections = [
  {
    title: "서비스 목적",
    body: "OJIK BMS는 BMS 플레이 데이터를 정리하고 시각화해 개인 기록 확인과 비교를 돕기 위한 서비스입니다. 게임 플레이 자체를 대체하거나 원저작물을 배포하는 목적은 아닙니다.",
  },
  {
    title: "금지 행위",
    body: "타인의 계정이나 데이터를 무단으로 업로드하거나, 허락없이 서비스 안정성을 해치는 무리한 자동화 요청을 보내거나, 운영을 방해할 목적의 악성 입력을 시도하는 행위는 금지합니다. 만약 OJIK BMS 사이트 활용한 서비스를 구현하고자 하시면 저에게 개인적으로 연락 주시길 바랍니다.",
  },
  {
    title: "제재 기준",
    body: "위 규칙을 반복적으로 위반하거나 다른 이용자 및 운영에 명확한 피해를 주는 경우, 사전 경고 없이 일부 기능 제한 또는 접근 차단이 이루어질 수 있습니다.",
  },
] as const;

export default function RulesPage() {
  return (
    <PublicInfoPageShell
      title="이용 규칙"
      description=""
    >
      {rulesSections.map((section) => (
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
