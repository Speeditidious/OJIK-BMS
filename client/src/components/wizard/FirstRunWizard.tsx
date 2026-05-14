import { ArrowLeft, ArrowRight, Check, LogIn, Sparkles } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import logoUrl from "../../assets/ojikbms_logo.png";
import type { AuthStatus, ClientConfig, LanguageCode } from "../../types";
import { LanguageSegmented } from "../language/LanguageSegmented";
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
  language: LanguageCode;
  onLanguageChange: (language: LanguageCode) => void;
}

export function FirstRunWizard({
  config,
  auth,
  isLoggingIn,
  onLogin,
  onUpdateConfig,
  onFinish,
  onPickError,
  language,
  onLanguageChange,
}: FirstRunWizardProps) {
  const { t } = useTranslation();
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
              <div className="wizard-card-eyebrow">{t("client.wizard.welcome.eyebrow")}</div>
              <div className="wizard-card-title">{t("client.wizard.welcome.title")}</div>
              <p className="wizard-card-body">
                {t("client.wizard.welcome.body")}
              </p>
              <div className="wizard-language-section">
                <div className="wizard-card-eyebrow">{t("client.wizard.language.eyebrow")}</div>
                <LanguageSegmented value={language} onChange={onLanguageChange} />
              </div>
              <div className="wizard-card-actions">
                <span />
                <Button
                  variant="primary"
                  leadingIcon={<ArrowRight size={15} aria-hidden="true" />}
                  onClick={goNext}
                >
                  {t("client.wizard.welcome.start")}
                </Button>
              </div>
            </>
          ) : null}

          {step === "login" ? (
            <>
              <div className="wizard-card-eyebrow">{t("client.wizard.login.eyebrow")}</div>
              <div className="wizard-card-title">{t("client.wizard.login.title")}</div>
              <p className="wizard-card-body">
                {t("client.wizard.login.body")}
              </p>
              <div className="wizard-card-content">
                {auth?.logged_in ? (
                  <div className="banner banner-info">
                    <Check size={16} aria-hidden="true" />
                    <div>
                      <div className="banner-title">{t("client.wizard.login.alreadyTitle")}</div>
                      <div className="banner-body">{t("client.wizard.login.alreadyBody")}</div>
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
                    {isLoggingIn ? t("client.wizard.login.buttonBusy") : t("client.wizard.login.button")}
                  </Button>
                )}
              </div>
              <WizardActions
                onPrev={goPrev}
                onNext={goNext}
                onSkip={goNext}
                nextLabel={auth?.logged_in ? t("common.actions.next") : t("common.actions.skip")}
                nextVariant={auth?.logged_in ? "primary" : "default"}
              />
            </>
          ) : null}

          {step === "lr2" ? (
            <>
              <div className="wizard-card-eyebrow">{t("client.wizard.lr2.eyebrow")}</div>
              <div className="wizard-card-title">{t("client.wizard.lr2.title")}</div>
              <p className="wizard-card-body">
                {t("client.wizard.lr2.body")}
              </p>
              <div className="wizard-card-content">
                <SourceCard
                  client="lr2"
                  config={config}
                  onUpdate={onUpdateConfig}
                  onPickError={onPickError}
                />
              </div>
              <WizardActions onPrev={goPrev} onNext={goNext} onSkip={goNext} />
            </>
          ) : null}

          {step === "beatoraja" ? (
            <>
              <div className="wizard-card-eyebrow">{t("client.wizard.beatoraja.eyebrow")}</div>
              <div className="wizard-card-title">{t("client.wizard.beatoraja.title")}</div>
              <p className="wizard-card-body">
                {t("client.wizard.beatoraja.body")}
              </p>
              <div className="wizard-card-content">
                <SourceCard
                  client="beatoraja"
                  config={config}
                  onUpdate={onUpdateConfig}
                  onPickError={onPickError}
                />
              </div>
              <WizardActions onPrev={goPrev} onNext={goNext} onSkip={goNext} />
            </>
          ) : null}

          {step === "ready" ? (
            <>
              <Sparkles size={28} style={{ color: "var(--primary)" }} aria-hidden="true" />
              <div className="wizard-card-eyebrow">{t("client.wizard.ready.eyebrow")}</div>
              <div className="wizard-card-title">{t("client.wizard.ready.title")}</div>
              <p className="wizard-card-body">
                {t("client.wizard.ready.body")}
              </p>
              <div className="wizard-card-actions">
                <Button variant="ghost" leadingIcon={<ArrowLeft size={15} aria-hidden="true" />} onClick={goPrev}>
                  {t("common.actions.back")}
                </Button>
                <Button variant="primary" leadingIcon={<ArrowRight size={15} aria-hidden="true" />} onClick={onFinish}>
                  {t("client.wizard.ready.finish")}
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
  nextLabel,
  nextVariant = "primary",
}: {
  onPrev: () => void;
  onNext: () => void;
  onSkip: () => void;
  nextLabel?: string;
  nextVariant?: "primary" | "default";
}) {
  const { t } = useTranslation();

  return (
    <div className="wizard-card-actions">
      <Button variant="ghost" leadingIcon={<ArrowLeft size={15} aria-hidden="true" />} onClick={onPrev}>
        {t("common.actions.back")}
      </Button>
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-ghost btn-sm wizard-skip" onClick={onSkip}>
          {t("common.actions.skip")}
        </button>
        <Button variant={nextVariant} leadingIcon={<ArrowRight size={15} aria-hidden="true" />} onClick={onNext}>
          {nextLabel ?? t("common.actions.next")}
        </Button>
      </div>
    </div>
  );
}
