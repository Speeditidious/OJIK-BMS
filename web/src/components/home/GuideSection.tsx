import Image, { type StaticImageData } from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  Download,
  LayoutDashboard,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import step1ClientDownloadImage from "../../../public/guide/step1_client_download.png";
import step2ClientSyncImage from "../../../public/guide/step2_client_sync.png";
import step3NavbarDropdownImage from "../../../public/guide/step3_navbar_dropdown.png";

type GuideImage = {
  src: StaticImageData;
  alt: string;
};

type GuideStep = {
  number: string;
  title: string;
  description: string;
  icon: LucideIcon;
  cta?: {
    href: string;
    label: string;
  };
  images: GuideImage[];
};

const guideSteps: GuideStep[] = [
  {
    number: "01",
    title: "클라이언트를 다운로드받습니다",
    description:
      "플레이 데이터를 서버에 동기화하려면 전용 클라이언트가 필요합니다. 클라이언트 다운로드 메뉴에서 exe파일을 받습니다.",
    icon: Download,
    cta: {
      href: "/download",
      label: "다운로드 페이지로 이동",
    },
    images: [
      {
        src: step1ClientDownloadImage,
        alt: "클라이언트 다운로드 페이지에서 설치 파일을 확인하는 화면",
      },
    ],
  },
  {
    number: "02",
    title: "클라이언트를 실행해 데이터를 동기화합니다",
    description:
      "처음에는 전체 동기화로 가지고 있는 차분 데이터를 포함해 기록을 서버에 보내시는 걸 추천드립니다. 이후 새로운 차분이 추가되지 않았으면 플레이 데이터만 보내기 위해 빠른 동기화를 추천드립니다 (훨씬 빠름).",
    icon: RefreshCw,
    images: [
      {
        src: step2ClientSyncImage,
        alt: "클라이언트에서 전체 동기화와 빠른 동기화 옵션을 확인하는 화면",
      },
    ],
  },
  {
    number: "03",
    title: "홈페이지에서 기록과 설정을 확인합니다",
    description:
      "로그인 후 우측 상단 프로필 사진을 눌러 대시보드에서 동기화 결과를 확인합니다. 같은 메뉴의 설정에서 선호 설정으로 들어가 표시 방식과 개인 선호를 조정할 수 있습니다.",
    icon: LayoutDashboard,
    images: [
      {
        src: step3NavbarDropdownImage,
        alt: "우측 상단 프로필 메뉴에서 대시보드와 설정으로 이동하는 화면",
      },
    ],
  },
];

function GuideStepImages({ step }: { step: GuideStep }) {
  if (step.images.length === 1) {
    const image = step.images[0];

    return (
      <div className="relative aspect-[16/10] overflow-hidden rounded-xl border border-border/70 bg-background/80">
        <Image
          src={image.src}
          alt={image.alt}
          fill
          sizes="(min-width: 1024px) 22rem, (min-width: 640px) 60vw, 100vw"
          className="object-cover object-top"
        />
      </div>
    );
  }

  const mainImages = step.images.slice(0, 2);
  const detailImages = step.images.slice(2);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {mainImages.map((image) => (
          <div
            key={image.src.src}
            className="relative aspect-[3/5] overflow-hidden rounded-xl border border-border/70 bg-background/80"
          >
            <Image
              src={image.src}
              alt={image.alt}
              fill
              sizes="(min-width: 1024px) 11rem, (min-width: 640px) 30vw, 50vw"
              className="object-cover object-top"
            />
          </div>
        ))}
      </div>
      {detailImages.map((image) => (
        <div
          key={image.src.src}
          className="relative aspect-video overflow-hidden rounded-xl border border-border/70 bg-background/80"
        >
          <Image
            src={image.src}
            alt={image.alt}
            fill
            sizes="(min-width: 1024px) 22rem, (min-width: 640px) 60vw, 100vw"
            className="object-cover object-top"
          />
        </div>
      ))}
    </div>
  );
}

export function GuideSection() {
  return (
    <section aria-labelledby="guide-title" className="border-t border-border/60 py-20">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <h2 id="guide-title" className="text-3xl font-bold tracking-tight">
            가이드
          </h2>
        </div>

        <div className="mt-14 space-y-8">
          {guideSteps.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === guideSteps.length - 1;

            return (
              <article
                key={step.number}
                className="grid gap-5 rounded-[1.75rem] border border-border/70 bg-card/85 p-5 shadow-sm backdrop-blur md:grid-cols-[auto_minmax(0,1fr)] md:gap-8 md:p-6"
              >
                <div className="hidden md:flex md:flex-col md:items-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-base font-semibold text-primary-foreground shadow-sm">
                    {step.number}
                  </div>
                  {!isLast ? (
                    <div
                      aria-hidden="true"
                      className="mt-3 w-px flex-1"
                      style={{
                        background:
                          "linear-gradient(180deg, hsl(var(--primary) / 0.6), hsl(var(--border)))",
                      }}
                    />
                  ) : null}
                </div>

                <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(220px,28%)] lg:items-start">
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="text-label font-medium text-primary md:hidden">{step.number}</div>
                        <h3 className="text-xl font-semibold tracking-tight">{step.title}</h3>
                      </div>
                    </div>

                    <p className="mt-4 max-w-2xl text-body leading-relaxed text-muted-foreground">
                      {step.description}
                    </p>

                    {step.cta ? (
                      <div className="mt-5">
                        <Button asChild variant="outline" size="lg" className="gap-2">
                          <Link href={step.cta.href}>
                            {step.cta.label}
                            <ArrowRight className="h-4 w-4" />
                          </Link>
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  <GuideStepImages step={step} />
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
