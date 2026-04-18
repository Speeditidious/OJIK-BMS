import { AlertTriangle } from "lucide-react";

export function BetaNoticeSection() {
  return (
    <section aria-labelledby="beta-notice-title" className="container mx-auto px-4 py-8">
      <div
        role="alert"
        className="rounded-2xl border px-6 py-5"
        style={{
          backgroundColor: "hsl(var(--warning) / 0.10)",
          borderColor: "hsl(var(--warning) / 0.35)",
        }}
      >
        <div className="flex items-start gap-3">
          <AlertTriangle
            className="mt-0.5 h-5 w-5 shrink-0"
            style={{ color: "hsl(var(--warning))" }}
            aria-hidden="true"
          />
          <div className="space-y-2">
            <h2 id="beta-notice-title" className="text-lg font-semibold tracking-tight">
              베타 테스트 진행 중입니다
            </h2>
            <p className="text-body leading-relaxed text-foreground">
              실무 경험 없는 초짜가 개발하는 중이라 중간중간에 서버에 올린 플레이데이터가
              변질되거나 삭제될 수 있습니다. 물론 그러지 않도록 항상 주의하고 있지만, 이 점은
              미리 양해 부탁드립니다.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
