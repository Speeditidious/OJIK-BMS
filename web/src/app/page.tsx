import Link from "next/link";
import Image from "next/image";
import { Music2, BarChart3, CalendarClock, Bot, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Navbar } from "@/components/layout/navbar";
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
    <main className="min-h-screen bg-background">
      <Navbar />

      {/* Hero section */}
      <section className="container mx-auto px-4 pt-16 pb-16 text-center">
        <div className="flex justify-center mb-6">
          <div className="flex items-center gap-3 bg-primary/10 text-primary px-4 py-2 rounded-full text-sm font-medium">
            <Music2 className="h-4 w-4" />
            BMS 유저들만을 위한 성과 관리 사이트
          </div>
        </div>

        <div className="flex justify-center mb-4">
          <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={128} height={128} />
        </div>

        <h1 className="text-5xl font-bold tracking-tight mb-6">
          OJIK BMS
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
          여러 BMS 구동기의 플레이 데이터를 통합 관리하고,
          즐겨찾기한 난이도표에 대한 성과를 한눈에 확인하세요.
          즐거운 리딸 되시길 바랍니다.
        </p>

        <div className="flex gap-4 justify-center flex-wrap">
          <LoginButton />
          <Link href="/download">
            <Button size="lg" variant="outline" className="gap-2">
              <Download className="h-5 w-5" />
              클라이언트 다운로드
            </Button>
          </Link>
        </div>
      </section>

      {/* Features section */}
      <section className="container mx-auto px-4 pb-24">
        <h2 className="text-3xl font-bold text-center mb-12">주요 기능</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-2">
                    <Icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription>{feature.description}</CardDescription>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Client download section */}
      <section className="border-t bg-muted/50">
        <div className="container mx-auto px-4 py-16 text-center">
          <Download className="h-12 w-12 text-primary mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-4">OJIK BMS 클라이언트</h2>
          <p className="text-muted-foreground max-w-lg mx-auto mb-8">
            LR2, Beatoraja 스코어 DB를 스캔하고 서버에 자동 동기화합니다.
            Windows용 GUI 클라이언트를 제공합니다.
          </p>
          <Link href="/download">
            <Button variant="outline" size="lg" className="gap-2">
              <Download className="h-4 w-4" />
              다운로드 페이지로
            </Button>
          </Link>
        </div>
      </section>
    </main>
  );
}
