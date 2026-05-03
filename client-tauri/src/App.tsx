import { RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { useAuthStore } from "./hooks/use-auth";
import { useConfigStore } from "./hooks/use-config";
import { useSyncStore } from "./hooks/use-sync";
import { useToastStore } from "./hooks/use-toast";
import { useUpdateStore } from "./hooks/use-update";
import { getDiagnosticsInfo, openDownloadPage, openSite } from "./tauri";
import type { ClientFilter, ClientType, DiagnosticsInfo, SyncRequest } from "./types";

const DEFAULT_APP_VERSION = "1.0.0.beta1";
const APP_VERSION = (import.meta.env.VITE_APP_VERSION ?? DEFAULT_APP_VERSION).replace(/^v/i, "");

export default function App() {
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
    ? "먼저 Discord 로그인이 필요합니다"
    : !anySourceReady
      ? "최소 한 개의 클라이언트 경로를 설정하세요"
      : isSyncRunning
        ? "이미 동기화 진행 중입니다"
        : undefined;

  // Auto-open update dialog when policy comes back with announcement.
  const lastDialogedAnnouncementId = useRef<string | null>(null);
  if (
    updater.policy?.update_available &&
    updater.policy.announcement &&
    lastDialogedAnnouncementId.current !== updater.policy.announcement.id &&
    !updateDialogOpen
  ) {
    lastDialogedAnnouncementId.current = updater.policy.announcement.id;
    setUpdateDialogOpen(true);
  }

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
        title: "다시 로그인이 필요해요",
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
  }, [toast]);

  // Auto-open failure dialog when an install error appears.
  if (updater.installError && !updateFailureOpen) {
    setUpdateFailureOpen(true);
  }

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
          title: "동기화를 시작할 수 없어요",
          message: msg,
        });
      }
    },
    [config, sync, toast],
  );

  const handleLogin = useCallback(async () => {
    try {
      const next = await login();
      if (next.logged_in) {
        setSessionExpired(false);
        toast.push({ tone: "success", message: "로그인되었습니다." });
      }
      return next;
    } catch (err) {
      toast.push({
        tone: "warn",
        title: "로그인을 진행할 수 없어요",
        message: err instanceof Error ? err.message : String(err),
      });
      return null;
    }
  }, [login, toast]);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
      toast.push({ tone: "info", message: "로그아웃되었습니다." });
    } catch (err) {
      toast.push({
        tone: "warn",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [logout, toast]);

  const handleManualUpdateCheck = useCallback(async () => {
    try {
      const policy = await updater.manualCheck();
      if (!policy.update_available) {
        toast.push({
          tone: "info",
          message: policy.message ?? "사용 가능한 업데이트가 없습니다.",
        });
      }
    } catch (err) {
      toast.push({
        tone: "warn",
        title: "업데이트를 확인할 수 없어요",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [updater, toast]);

  const handleOpenSite = useCallback(async () => {
    try {
      await openSite();
    } catch (err) {
      toast.push({
        tone: "warn",
        title: "사이트를 열 수 없어요",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, [toast]);

  const handleOpenDownloadPage = useCallback(async () => {
    try {
      const url = await openDownloadPage();
      toast.push({ tone: "info", message: `다운로드 페이지를 열었습니다: ${url}` });
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
    toast.push({ tone: "info", message: "숨긴 업데이트 알림을 다시 표시합니다." });
  }, [config, update, toast]);

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
        <p>클라이언트 설정을 불러오는 중입니다.</p>
      </main>
    );
  }

  if (loadState === "error" || !config) {
    return (
      <main className="app-shell app-center">
        <ShieldAlert size={32} aria-hidden="true" />
        <p>설정을 불러오지 못했습니다.</p>
        {error ? <pre>{error}</pre> : null}
      </main>
    );
  }

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
          onPickError={(msg) =>
            toast.push({ tone: "warn", title: "경로 선택 오류", message: msg })
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
              onQuickSync={() => handleStartSync(client, false)}
              onFullSync={() => handleStartSync(client, true)}
              syncDisabled={!auth?.logged_in || isSyncRunning}
              syncDisabledReason={
                !auth?.logged_in ? "먼저 Discord 로그인이 필요합니다" : isSyncRunning ? "동기화 진행 중" : undefined
              }
              onPickError={(msg) => toast.push({ tone: "warn", title: "경로 선택 오류", message: msg })}
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
              <div className="card-title">진행 상황</div>
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
            window.open(url, "_blank", "noopener,noreferrer");
          }}
        />

        <LogViewer
          logs={sync.logs}
          overflowed={sync.overflowed}
          onClear={sync.clearLogs}
          onCopy={(text) => {
            navigator.clipboard
              ?.writeText(text)
              .then(() => toast.push({ tone: "success", message: "로그를 클립보드에 복사했습니다." }))
              .catch(() => toast.push({ tone: "warn", message: "클립보드 접근에 실패했습니다." }));
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
          configDir: diagnosticsInfo?.config_dir,
          logsDir: diagnosticsInfo?.logs_dir,
        }}
        config={config}
        onCheckUpdate={handleManualUpdateCheck}
        onOpenDownloadPage={handleOpenDownloadPage}
        onResetUpdateDismissals={handleResetUpdateDismissals}
        isCheckingUpdate={updater.isChecking}
      />

      {updater.policy?.announcement ? (
        <UpdateDialog
          open={updateDialogOpen}
          announcement={updater.policy.announcement}
          isInstalling={updater.isInstalling}
          downloadProgress={updater.downloadProgress}
          onInstall={() => {
            const id = updater.policy?.announcement?.id;
            if (id) updater.install(id);
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
          onOpenReleasePage={(url) => window.open(url, "_blank", "noopener,noreferrer")}
          onClose={() => setUpdateDialogOpen(false)}
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
  if (saveState === "idle") return null;
  const text =
    saveState === "saving" ? "자동 저장 중…" : saveState === "saved" ? "저장됨" : "저장 실패";
  const color =
    saveState === "error" ? "var(--danger)" : saveState === "saved" ? "var(--success)" : "var(--muted)";
  return <span style={{ color, fontSize: "0.78rem" }}>{text}</span>;
}
