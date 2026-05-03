import { ArrowLeft, ArrowRight, Check, LogIn, Sparkles } from "lucide-react";
import { useState } from "react";

import logoUrl from "../../assets/ojikbms_logo.png";
import type { AuthStatus, ClientConfig } from "../../types";
import { Button } from "../primitives/Button";
import { SourceCard } from "../source/SourceCard";

type StepId = "welcome" | "login" | "lr2" | "beatoraja" | "ready";

const STEPS: StepId[] = ["welcome", "login", "lr2", "beatoraja", "ready"];

export interface FirstRunWizardProps {
  config: ClientConfig;
  auth: AuthStatus | null;
  isLoggingIn: boolean;
  onLogin: () => AuthStatus | null | void | Promise<AuthStatus | null | void>;
  onUpdateConfig: (patch: Partial<ClientConfig>) => void;
  onFinish: () => void;
  onPickError?: (message: string) => void;
}

export function FirstRunWizard({
  config,
  auth,
  isLoggingIn,
  onLogin,
  onUpdateConfig,
  onFinish,
  onPickError,
}: FirstRunWizardProps) {
  const [stepIdx, setStepIdx] = useState(0);
  const step = STEPS[stepIdx];

  const goNext = () => setStepIdx((i) => Math.min(i + 1, STEPS.length - 1));
  const goPrev = () => setStepIdx((i) => Math.max(i - 1, 0));
  const handleLogin = async () => {
    const next = await onLogin();
    if (next?.logged_in) {
      goNext();
    }
  };

  return (
    <div className="wizard">
      <div className="wizard-shell">
        <div className="wizard-progress" aria-hidden="true">
          {STEPS.map((s, i) => (
            <span
              key={s}
              className={`wizard-step-pip${i === stepIdx ? " is-active" : ""}${i < stepIdx ? " is-done" : ""}`}
            />
          ))}
        </div>

        <article className="wizard-card fade-in">
          {step === "welcome" ? (
            <>
              <img src={logoUrl} alt="" style={{ width: 56, height: 56 }} />
              <div className="wizard-card-eyebrow">OJIKBMS 클라이언트 설정 안내</div>
              <div className="wizard-card-title">첫 동기화를 위한 설정을 안내합니다.</div>
              <p className="wizard-card-body">
                이번 세션에서 Discord 로그인, LR2/beatoraja 로컬 DB 경로 설정, 첫 동기화까지 진행할 예정입니다.
                언제든 “건너뛰기” 눌러서 나중에 설정해도 괜찮습니다.
              </p>
              <div className="wizard-card-actions">
                <span />
                <Button
                  variant="primary"
                  leadingIcon={<ArrowRight size={15} aria-hidden="true" />}
                  onClick={goNext}
                >
                  시작하기
                </Button>
              </div>
            </>
          ) : null}

          {step === "login" ? (
            <>
              <div className="wizard-card-eyebrow">1단계 · 로그인</div>
              <div className="wizard-card-title">Discord 계정으로 로그인하세요</div>
              <p className="wizard-card-body">
                플레이 데이터는 여기서 로그인한 계정에 묶입니다.
                동기화 후 OJIKBMS 사이트에서 동일한 계정으로 로그인하면 데이터를 보실 수 있습니다.
              </p>
              <div className="wizard-card-content">
                {auth?.logged_in ? (
                  <div className="banner banner-info">
                    <Check size={16} aria-hidden="true" />
                    <div>
                      <div className="banner-title">이미 로그인되어 있어요</div>
                      <div className="banner-body">다음 단계에서 경로를 설정해 주세요.</div>
                    </div>
                  </div>
                ) : (
                  <Button
                    variant="primary"
                    size="lg"
                    leadingIcon={<LogIn size={16} aria-hidden="true" />}
                    onClick={handleLogin}
                    disabled={isLoggingIn}
                  >
                    {isLoggingIn ? "Discord 로그인 진행 중…" : "Discord로 로그인"}
                  </Button>
                )}
              </div>
              <WizardActions
                onPrev={goPrev}
                onNext={goNext}
                onSkip={goNext}
                nextLabel={auth?.logged_in ? "다음" : "건너뛰기"}
                nextVariant={auth?.logged_in ? "primary" : "default"}
              />
            </>
          ) : null}

          {step === "lr2" ? (
            <>
              <div className="wizard-card-eyebrow">2단계 · LR2 경로</div>
              <div className="wizard-card-title">LR2를 사용하지 않으신다면 "건너뛰기"를 눌러주세요.</div>
              <p className="wizard-card-body">
                LR2 플레이 기록 DB와 song.db 경로를 설정하세요.
                플레이 기록 DB는 필수이며, song.db를 설정하지 않으면 서버에 없는 차분이 (알 수 없음)으로 표시될 수 있습니다.
              </p>
              <div className="wizard-card-content">
                <SourceCard
                  client="lr2"
                  config={config}
                  onUpdate={onUpdateConfig}
                  onQuickSync={() => {}}
                  onFullSync={() => {}}
                  syncDisabled
                  syncDisabledReason="동기화는 마지막 단계에서 시작합니다"
                  onPickError={onPickError}
                />
              </div>
              <WizardActions onPrev={goPrev} onNext={goNext} onSkip={goNext} />
            </>
          ) : null}

          {step === "beatoraja" ? (
            <>
              <div className="wizard-card-eyebrow">3단계 · beatoraja 경로</div>
              <div className="wizard-card-title">beatoraja를 사용하지 않으신다면 “건너뛰기”를 눌러주세요.</div>
              <p className="wizard-card-body">
                beatoraja 플레이 기록 DB 폴더와 songdata.db, songinfo.db 경로를 설정하세요.
                플레이 기록 DB 폴더는 필수이며, songdata.db 또는 songinfo.db를 설정하지 않으면 일부 차분 정보 보강이 제한될 수 있습니다.
              </p>
              <div className="wizard-card-content">
                <SourceCard
                  client="beatoraja"
                  config={config}
                  onUpdate={onUpdateConfig}
                  onQuickSync={() => {}}
                  onFullSync={() => {}}
                  syncDisabled
                  syncDisabledReason="동기화는 마지막 단계에서 시작합니다"
                  onPickError={onPickError}
                />
              </div>
              <WizardActions onPrev={goPrev} onNext={goNext} onSkip={goNext} />
            </>
          ) : null}

          {step === "ready" ? (
            <>
              <Sparkles size={28} style={{ color: "var(--primary)" }} aria-hidden="true" />
              <div className="wizard-card-eyebrow">설정 완료</div>
              <div className="wizard-card-title">대시보드로 이동해 첫 동기화를 시작하세요</div>
              <p className="wizard-card-body">
                대시보드에서 “전체 동기화” 버튼을 누르면 바로 진행됩니다.
                이후 새로운 차분이 추가되지 않았으면 플레이 데이터만 보내기 위해 “빠른 동기화” 버튼을 누르시는 것을 추천드립니다.
              </p>
              <div className="wizard-card-actions">
                <Button variant="ghost" leadingIcon={<ArrowLeft size={15} aria-hidden="true" />} onClick={goPrev}>
                  뒤로
                </Button>
                <Button variant="primary" leadingIcon={<ArrowRight size={15} aria-hidden="true" />} onClick={onFinish}>
                  대시보드로 이동
                </Button>
              </div>
            </>
          ) : null}
        </article>
      </div>
    </div>
  );
}

function WizardActions({
  onPrev,
  onNext,
  onSkip,
  nextLabel = "다음",
  nextVariant = "primary",
}: {
  onPrev: () => void;
  onNext: () => void;
  onSkip: () => void;
  nextLabel?: string;
  nextVariant?: "primary" | "default";
}) {
  return (
    <div className="wizard-card-actions">
      <Button variant="ghost" leadingIcon={<ArrowLeft size={15} aria-hidden="true" />} onClick={onPrev}>
        뒤로
      </Button>
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-ghost btn-sm wizard-skip" onClick={onSkip}>
          건너뛰기
        </button>
        <Button variant={nextVariant} leadingIcon={<ArrowRight size={15} aria-hidden="true" />} onClick={onNext}>
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}
