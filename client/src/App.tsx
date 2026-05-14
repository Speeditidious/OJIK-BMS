import { RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { DiagnosticsPanel } from "./components/about/DiagnosticsPanel";
import { LogViewer } from "./components/log/LogViewer";
import { AboutFooter } from "./components/layout/AboutFooter";
import { BannerStack } from "./components/layout/BannerStack";
import { Topbar } from "./components/layout/Topbar";
import { SourceCard } from "./components/source/SourceCard";
import { ResultSummary } from "./components/sync/ResultSummary";
import { SyncHero, SyncStubNotice } from "./components/sync/SyncHero";
import { SyncProgressCard } from "./components/sync/SyncProgressCard";
import { UpdateDialog } from "./components/update/UpdateDialog";
import { UpdateFailureDialog } from "./components/update/UpdateFailureDialog";
import { FirstRunWizard } from "./components/wizard/FirstRunWizard";
import { ToastStack } from "./components/primitives/Toast";
import { subscribe } from "./lib/tauri-events";
import { changeClientLanguage } from "./lib/i18n/client";
import { useAuthStore } from "./hooks/use-auth";
import { useConfigStore } from "./hooks/use-config";
import { useSyncStore } from "./hooks/use-sync";
import { useToastStore } from "./hooks/use-toast";
import { useUpdateStore } from "./hooks/use-update";
import { getDiagnosticsInfo, openDownloadPage, openExternalUrl, openSite } from "./tauri";
import type { ClientFilter, ClientType, DiagnosticsInfo, LanguageCode, SyncRequest } from "./types";

const DEFAULT_APP_VERSION = "1.0.0.beta1";
const APP_VERSION = (import.meta.env.VITE_APP_VERSION ?? DEFAULT_APP_VERSION).replace(/^v/i, "");

export default function App() {
  const { t } = useTranslation();
  const { config, loadState, saveState, error, update } = useConfigStore();
  const { status: auth, isLoggingIn, login, logout } = useAuthStore();
  const sync = useSyncStore();
  const updater = useUpdateStore();
  const toast = useToastStore();

  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [updateFailureOpen, setUpdateFailureOpen] = useState(false);
  const [wizardDismissed, setWizardDismissed] = useState(false);
  const [stubMessage, setStubMessage] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [diagnosticsInfo, setDiagnosticsInfo] = useState<DiagnosticsInfo | null>(null);
  const shouldShowFirstRunWizard = useRef<boolean | null>(null);

  const lastTickerLog = useMemo(() => sync.logs[sync.logs.length - 1]?.message ?? null, [sync.logs]);
  const configLanguage = config?.language;

  const isSyncRunning = sync.state === "running";
  if (config && shouldShowFirstRunWizard.current === null) {
    shouldShowFirstRunWizard.current = !config.lr2_db_path && !config.beatoraja_db_dir;
  }
  const showWizard = !wizardDismissed && config && shouldShowFirstRunWizard.current === true;

  const lr2Ready = Boolean(config?.lr2_db_path);
  const beaReady = Boolean(config?.beatoraja_db_dir);
  const anySourceReady = lr2Ready || beaReady;

  const syncDisabledGlobal = !auth?.logged_in || !anySourceReady || isSyncRunning;
  const syncDisabledReason = !auth?.logged_in
    ? t("client.app.syncDisabled.loginRequired")
    : !anySourceReady
      ? t("client.app.syncDisabled.pathRequired")
      : isSyncRunning
        ? t("client.app.syncDisabled.alreadyRunning")
        : undefined;

  // Auto-open update dialog when policy comes back with announcement.
  const lastAutoOpenedAnnouncementId = useRef<string | null>(null);

  useEffect(() => {
    const announcement = updater.policy?.update_available
      ? updater.policy.announcement
      : null;
    if (!announcement) return;
    if (lastAutoOpenedAnnouncementId.current === announcement.id) return;
    lastAutoOpenedAnnouncementId.current = announcement.id;
    setUpdateDialogOpen(true);
  }, [updater.policy]);

  useEffect(() => {
    let cancelled = false;
    getDiagnosticsInfo()
      .then((next) => {
        if (!cancelled) setDiagnosticsInfo(next);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let unlisten: (() => void) | null = null;
    let active = true;
    subscribe<{ sync_run_id: string; message: string }>("auth:reauth-required", (payload) => {
      setSessionExpired(true);
      toast.push({
        tone: "warn",
        title: t("client.app.toasts.reauthRequired"),
        message: payload.message,
      });
    }).then((fn) => {
      if (active) {
        unlisten = fn;
      } else {
        fn();
      }
    });
    return () => {
      active = false;
      unlisten?.();
    };
  }, [toast, t]);

  // Auto-open failure dialog when an install error appears.
  useEffect(() => {
    if (updater.installError && !updateFailureOpen) {
      setUpdateFailureOpen(true);
    }
  }, [updater.installError, updateFailureOpen]);

  useEffect(() => {
    if (configLanguage) {
      changeClientLanguage(configLanguage);
    }
  }, [configLanguage]);

  const handleStartSync = useCallback(
    async (filter: ClientFilter, fullSync: boolean) => {
      if (!config) return;
      const request: SyncRequest = { client_filter: filter, full_sync: fullSync };
      try {
        await sync.start(request);
        setStubMessage(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setStubMessage(msg);
        toast.push({
          tone: "warn",
          title: t("client.app.toasts.syncUnavailableTitle"),
          message: msg,
        });
      }
    },
    [config, sync, toast, t],
  );

  const handleLogin = useCallback(async () => {
    try {
      const next = await login();
      if (next.logged_in) {
        setSessionExpired(false);
        toast.push({ tone: "success", message: t("client.app.toasts.loginSuccess") });
      }
      return next;
    } catch (err) {
      const rawMsg = err instanceof Error ? err.message : String(err);
      // Translate stable error codes emitted by tauri.ts
      const msg = rawMsg.startsWith("client.") ? t(rawMsg) : rawMsg;
      toast.push({
        tone: "warn",
        title: t("client.app.toasts.loginFailedTitle"),
        message: msg,
      });
      return null;
    }
  }, [login, toast, t]);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
      toast.push({ tone: "info", message: t("client.app.toasts.logoutSuccess") });
    } catch (err) {
      toast.push({
        tone: "warn",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [logout, toast, t]);

  const handleManualUpdateCheck = useCallback(async () => {
    try {
      const policy = await updater.manualCheck();
      if (policy.update_available && policy.announcement) {
        // Force-reopen even if user closed the dialog earlier (X button).
        lastAutoOpenedAnnouncementId.current = policy.announcement.id;
        setUpdateDialogOpen(true);
      } else {
        const rawMsg = policy.message ?? "client.app.toasts.updateUnavailable";
        const msg = rawMsg.startsWith("client.") ? t(rawMsg) : rawMsg;
        toast.push({ tone: "info", message: msg });
      }
    } catch (err) {
      toast.push({
        tone: "warn",
        title: t("client.app.toasts.updateCheckFailedTitle"),
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [updater, toast, t]);

  const handleOpenSite = useCallback(async () => {
    try {
      await openSite();
    } catch (err) {
      toast.push({
        tone: "warn",
        title: t("client.app.toasts.openSiteFailedTitle"),
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [toast, t]);

  const handleOpenDownloadPage = useCallback(async () => {
    try {
      await openDownloadPage();
    } catch (err) {
      toast.push({
        tone: "warn",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [toast]);

  const handleResetUpdateDismissals = useCallback(() => {
    if (!config) return;
    update({
      dismissed_update_id: null,
      dismissed_update_until: null,
      skipped_update_version: null,
    });
    toast.push({ tone: "info", message: t("client.app.toasts.resetUpdateDismissals") });
  }, [config, update, toast, t]);

  const handleClearUpdateFailure = useCallback(() => {
    if (!config) return;
    update({
      last_update_failure_at: null,
      last_update_failure_version: null,
      last_update_failure_stage: null,
      last_update_failure_message: null,
    });
  }, [config, update]);

  if (loadState === "loading") {
    return (
      <main className="app-shell app-center">
        <RefreshCw className="spin" size={28} aria-hidden="true" />
        <p>{t("client.app.loadingConfig")}</p>
      </main>
    );
  }

  if (loadState === "error" || !config) {
    return (
      <main className="app-shell app-center">
        <ShieldAlert size={32} aria-hidden="true" />
        <p>{t("client.app.configLoadFailed")}</p>
        {error ? <pre>{error}</pre> : null}
      </main>
    );
  }

  const handleLanguageChange = (language: LanguageCode) => {
    changeClientLanguage(language);
    update({ language });
  };

  if (showWizard) {
    return (
      <>
        <FirstRunWizard
          config={config}
          auth={auth}
          isLoggingIn={isLoggingIn}
          onLogin={handleLogin}
          onUpdateConfig={update}
          onFinish={() => setWizardDismissed(true)}
          language={config.language}
          onLanguageChange={handleLanguageChange}
          onPickError={(msg) =>
            toast.push({ tone: "warn", title: t("client.app.toasts.pathPickErrorTitle"), message: msg })
          }
        />
        <ToastStack toasts={toast.toasts} onDismiss={toast.dismiss} />
      </>
    );
  }

  return (
    <>
      <main className="app-shell">
        <Topbar
          auth={auth}
          onLogin={handleLogin}
          onLogout={handleLogout}
          onOpenDiagnostics={() => setDiagnosticsOpen(true)}
          onOpenSite={handleOpenSite}
          isLoggingIn={isLoggingIn}
          language={config.language}
          onLanguageChange={handleLanguageChange}
        />

        <BannerStack
          auth={auth}
          config={config}
          policy={updater.policy}
          syncRunning={isSyncRunning}
          sessionExpired={sessionExpired}
          onLogin={handleLogin}
          onInstallUpdate={() => {
            const id = updater.policy?.announcement?.id;
            if (id) updater.install(id);
          }}
          onOpenDownloadPage={handleOpenDownloadPage}
          onClearUpdateFailure={handleClearUpdateFailure}
        />

        <section className="source-grid">
          {(["lr2", "beatoraja"] as ClientType[]).map((client) => (
            <SourceCard
              key={client}
              client={client}
              config={config}
              onUpdate={update}
              onPickError={(msg) => toast.push({ tone: "warn", title: t("client.app.toasts.pathPickErrorTitle"), message: msg })}
            />
          ))}
        </section>

        <SyncHero
          config={config}
          lastResult={sync.lastResult}
          syncRunning={isSyncRunning}
          syncDisabled={syncDisabledGlobal}
          syncDisabledReason={syncDisabledReason}
          onQuickSync={() => handleStartSync("all", false)}
          onFullSync={() => handleStartSync("all", true)}
          onCancel={() => sync.cancel()}
        />

        {isSyncRunning ? (
          <section className="card">
            <header className="card-hd">
              <div className="card-title">{t("client.app.progressTitle")}</div>
              <SaveStateBadge saveState={saveState} />
            </header>
            <div className="card-bd">
              <SyncProgressCard stage={sync.stage} progress={sync.progress} ticker={lastTickerLog} />
            </div>
          </section>
        ) : null}

        {stubMessage && !isSyncRunning ? <SyncStubNotice message={stubMessage} /> : null}

        <ResultSummary
          result={sync.lastResult}
          onOpenResultUrl={(url) => {
            void openExternalUrl(url).catch((err) =>
              toast.push({
                tone: "warn",
                title: t("client.app.toasts.openSiteFailedTitle"),
                message: err instanceof Error ? err.message : String(err),
              }),
            );
          }}
        />

        <LogViewer
          logs={sync.logs}
          debugMode={config.debug_mode}
          onClear={sync.clearLogs}
          onToggleDebugMode={() => update({ debug_mode: !config.debug_mode })}
          onCopy={(text) => {
            navigator.clipboard
              ?.writeText(text)
              .then(() => toast.push({ tone: "success", message: t("client.app.toasts.logsCopied") }))
              .catch(() => toast.push({ tone: "warn", message: t("client.app.toasts.clipboardFailed") }));
          }}
        />

        <AboutFooter
          version={APP_VERSION}
          channel={config.update_channel || "stable"}
          onOpenDownloadPage={handleOpenDownloadPage}
          onOpenSite={handleOpenSite}
        />
      </main>

      <DiagnosticsPanel
        open={diagnosticsOpen}
        onClose={() => setDiagnosticsOpen(false)}
        info={{
          version: APP_VERSION,
          channel: config.update_channel || "stable",
          apiUrl: config.api_url,
          os: diagnosticsInfo?.os,
          webview: diagnosticsInfo?.webview,
          exePath: diagnosticsInfo?.exe_path,
          configDir: diagnosticsInfo?.config_dir,
          logsDir: diagnosticsInfo?.logs_dir,
        }}
        config={config}
        onCheckUpdate={handleManualUpdateCheck}
        onResetUpdateDismissals={handleResetUpdateDismissals}
        onToggleVerboseDiskLogging={(next) => update({ verbose_disk_logging: next })}
        isCheckingUpdate={updater.isChecking}
      />

      {updater.policy?.announcement ? (
        <UpdateDialog
          open={updateDialogOpen}
          announcement={updater.policy.announcement}
          isInstalling={updater.isInstalling}
          downloadProgress={updater.downloadProgress}
          supportsAutoInstall={Boolean(updater.policy.announcement.supports_auto_install)}
          onInstall={() => {
            const announcement = updater.policy?.announcement;
            if (!announcement) return;
            if (!announcement.supports_auto_install) {
              void handleOpenDownloadPage();
              return;
            }
            updater.install(announcement.id);
          }}
          onLater={() => {
            const id = updater.policy?.announcement?.id;
            if (id) {
              const until = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
              update({ dismissed_update_id: id, dismissed_update_until: until });
            }
            setUpdateDialogOpen(false);
          }}
          onSkip={() => {
            const version = updater.policy?.announcement?.version;
            if (version) update({ skipped_update_version: version });
            setUpdateDialogOpen(false);
          }}
          onOpenReleasePage={(url) => {
            void openExternalUrl(url).catch((err) =>
              toast.push({
                tone: "warn",
                title: t("client.app.toasts.openReleaseFailedTitle"),
                message: err instanceof Error ? err.message : String(err),
              }),
            );
          }}
          onClose={() => {
            setUpdateDialogOpen(false);
            // Allow background re-poll to reopen the same announcement next cycle.
            lastAutoOpenedAnnouncementId.current = null;
          }}
        />
      ) : null}

      {updater.installError ? (
        <UpdateFailureDialog
          open={updateFailureOpen}
          error={updater.installError}
          mandatory={Boolean(updater.policy?.announcement?.mandatory)}
          onRetry={() => {
            const id = updater.policy?.announcement?.id;
            if (id) updater.install(id);
          }}
          onOpenDownloadPage={handleOpenDownloadPage}
          onClose={() => setUpdateFailureOpen(false)}
        />
      ) : null}

      <ToastStack toasts={toast.toasts} onDismiss={toast.dismiss} />
    </>
  );
}

function SaveStateBadge({ saveState }: { saveState: "idle" | "saving" | "saved" | "error" }) {
  const { t } = useTranslation();
  if (saveState === "idle") return null;
  const text =
    saveState === "saving"
      ? t("client.app.saveState.saving")
      : saveState === "saved"
        ? t("client.app.saveState.saved")
        : t("client.app.saveState.failed");
  const color =
    saveState === "error" ? "var(--danger)" : saveState === "saved" ? "var(--success)" : "var(--muted)";
  return <span style={{ color, fontSize: "0.78rem" }}>{text}</span>;
}
