import Link from "next/link";
import Image from "next/image";
import { Music2, BarChart3, CalendarClock, Bot, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BetaNoticeSection } from "@/components/home/BetaNoticeSection";
import { GuideSection } from "@/components/home/GuideSection";
import { Navbar } from "@/components/layout/navbar";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { LoginButton } from "@/components/home/LoginButton";

const features = [
  {
    icon: BarChart3,
    title: "플레이 분석",
    description: "난이도표 별 플레이 데이터를 시각화하여 실력 향상 추이를 확인할 수 있습니다.",
  },
  {
    icon: CalendarClock,
    title: "LR2 날짜별 기록 추적",
    description: "LR2는 플레이 기록 데이터베이스에 날짜가 저장되지 않아 언제 기록을 달성했는지 추적하기 어려웠습니다. 이제 서버에 기록한 시간을 기반으로 추적할 수 있습니다.",
  },
  {
    icon: Music2,
    title: "커스텀 테이블/코스 (예정)",
    description: "추가 난이도표 등록 뿐만 아니라, 나만의 난이도표와 코스를 쉽게 만들어 공유하고 관리할 수 있습니다.",
  },
  {
    icon: Bot,
    title: "AI 챗봇 (예정)",
    description: "BMS 관련 질문, 곡 추천, 플레이 기록 기반 조언을 해주는 챗봇과 대화할 수 있습니다.",
  },
];

export default function HomePage() {
  return (
    <>
      <main className="min-h-screen bg-background">
        <Navbar />

        <section className="relative overflow-hidden">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 top-0 h-[32rem]"
            style={{
              background:
                "radial-gradient(circle at top, hsl(var(--primary) / 0.22), hsl(var(--background) / 0) 62%)",
            }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 top-24 h-64 w-64 rounded-full blur-3xl"
            style={{ backgroundColor: "hsl(var(--accent) / 0.15)" }}
          />

          <div className="container relative mx-auto px-4 pb-16 pt-16 md:pb-20 md:pt-20">
            <div className="mx-auto max-w-5xl text-center">
              <div className="flex justify-center">
                <div className="flex items-center gap-3 rounded-full border border-primary/20 bg-background/70 px-4 py-2 text-body font-medium text-primary shadow-sm backdrop-blur">
                  <Music2 className="h-4 w-4" />
                  BMS 유저들만을 위한 성과 관리 사이트
                </div>
              </div>

              <div className="mt-8 flex justify-center">
                <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={128} height={128} priority />
              </div>

              <h1 className="mt-8 text-hero font-bold tracking-tight">OJIK BMS</h1>
              <p className="mx-auto mt-6 max-w-3xl text-xl leading-relaxed text-muted-foreground">
                여러 BMS 구동기의 플레이 데이터를 통합 관리하고, 즐겨찾기한 난이도표에 대한 성과를
                한눈에 확인하세요. 즐거운 리딸 되시길 바랍니다.
              </p>

              <div className="mt-10 flex flex-wrap justify-center gap-4">
                <LoginButton />
                <Link href="/download">
                  <Button size="lg" variant="outline" className="gap-2 border-border bg-background/85">
                    <Download className="h-5 w-5" />
                    클라이언트 다운로드
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        <BetaNoticeSection />

        <section className="container mx-auto px-4 py-20">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="text-3xl font-bold tracking-tight">주요 기능</h2>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-4">
            {features.map((feature, index) => {
              const Icon = feature.icon;

              return (
                <Card
                  key={feature.title}
                  className="border-border/70 bg-card/85 shadow-sm transition-colors hover:border-primary/40"
                >
                  <CardHeader>
                    <div className="mb-4 flex items-center justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                        <Icon className="h-6 w-6" />
                      </div>
                      <span className="text-label font-medium text-muted-foreground">
                        {`0${index + 1}`}
                      </span>
                    </div>
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-body leading-relaxed text-muted-foreground">
                      {feature.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </section>

        <GuideSection />
      </main>
      <SiteFooter />
    </>
  );
}
