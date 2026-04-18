import { PublicInfoPageShell } from "@/components/layout/PublicInfoPageShell";

const legalSections = [
  {
    title: "개인정보 처리 안내",
    body: "로그인 및 서비스 제공 과정에서 계정 식별에 필요한 최소 정보와 사용자가 업로드한 플레이 데이터가 저장될 수 있습니다. 운영 목적과 직접 관계없는 개인정보 수집은 지양합니다.",
  },
  {
    title: "쿠키 / 로컬 스토리지",
    body: "로그인 상태 유지, 테마 설정, 기본 UI 선호값 저장을 위해 브라우저 저장소가 사용될 수 있습니다. 저장 항목은 서비스 동작과 편의성 향상을 위한 범위로 제한합니다.",
  },
  {
    title: "BMS 저작권 고지",
    body: "이 서비스는 BMS 플레이 기록과 메타데이터 정리를 돕기 위한 도구이며, 각 악곡과 BMS 콘텐츠의 저작권은 원저작자 및 배포처에 귀속됩니다. 저작권이 있는 원본 콘텐츠 자체를 배포하려는 목적이 아닙니다.",
  },
  {
    title: "면책 조항",
    body: "베타 운영 중에는 서비스 중단, 데이터 오류, 기능 변경이 예고 없이 발생할 수 있습니다. 운영자는 문제를 완화하려고 노력하지만, 베타 환경에서 발생한 모든 간접 손해를 보장할 수는 없습니다.",
  },
  {
    title: "저작권 침해 / 삭제 요청",
    body: "표시되는 정보나 링크가 권리 침해로 판단된다면 제보해주세요. 확인 가능한 근거와 함께 알려주시면 가능한 한 빠르게 검토하고 조치하겠습니다.",
  },
] as const;

export default function LegalPage() {
  return (
    <PublicInfoPageShell
      title="법적 고지"
      description="이 문서는 법률 자문을 대체하지는 않지만, 현재 서비스가 어떤 범위로 운영되고 있는지와 이용자가 알아야 할 기본 고지를 정리한 페이지입니다."
    >
      {legalSections.map((section) => (
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
