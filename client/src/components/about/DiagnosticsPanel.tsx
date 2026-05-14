import { FileText, RefreshCw, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ClientConfig } from "../../types";
import { Button } from "../primitives/Button";
import { Dialog } from "../primitives/Dialog";

export interface DiagnosticsInfo {
  version: string;
  channel: string;
  os?: string | null;
  webview?: string | null;
  apiUrl: string;
  exePath?: string | null;
  configDir?: string | null;
  logsDir?: string | null;
}

export function DiagnosticsPanel({
  open,
  onClose,
  info,
  config,
  onCheckUpdate,
  onOpenLogFile,
  onResetUpdateDismissals,
  onToggleVerboseDiskLogging,
  isCheckingUpdate,
}: {
  open: boolean;
  onClose: () => void;
  info: DiagnosticsInfo;
  config: ClientConfig | null;
  onCheckUpdate: () => void;
  onOpenLogFile?: () => void;
  onResetUpdateDismissals: () => void;
  onToggleVerboseDiskLogging?: (next: boolean) => void;
  isCheckingUpdate: boolean;
}) {
  const { t } = useTranslation();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("client.diagnostics.title")}
      footer={
        <Button variant="ghost" onClick={onClose}>
          {t("client.diagnostics.close")}
        </Button>
      }
    >
      <div style={{ display: "grid", gap: 14 }}>
        <DiagSection title={t("client.diagnostics.sectionApp")}>
          <DiagRow label={t("client.diagnostics.version")} value={`v${info.version}`} />
          <DiagRow label={t("client.diagnostics.channel")} value={info.channel} />
          {info.os ? <DiagRow label="OS" value={info.os} /> : null}
          {info.webview ? <DiagRow label="WebView2" value={info.webview} /> : null}
          <DiagRow label="API URL" value={info.apiUrl} />
          {info.exePath ? <DiagRow label={t("client.diagnostics.exePath")} value={info.exePath} mono /> : null}
          {info.configDir ? <DiagRow label={t("client.diagnostics.configDir")} value={info.configDir} mono /> : null}
          {info.logsDir ? <DiagRow label={t("client.diagnostics.logsDir")} value={info.logsDir} mono /> : null}
          {config && onToggleVerboseDiskLogging ? (
            <VerboseDiskLoggingRow
              enabled={config.verbose_disk_logging}
              onToggle={onToggleVerboseDiskLogging}
            />
          ) : null}
        </DiagSection>

        <DiagSection title={t("client.diagnostics.sectionUpdate")}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button
              size="sm"
              leadingIcon={
                <RefreshCw size={14} aria-hidden="true" className={isCheckingUpdate ? "spin" : undefined} />
              }
              onClick={onCheckUpdate}
              disabled={isCheckingUpdate}
            >
              {t("client.diagnostics.checkUpdate")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              leadingIcon={<RotateCcw size={14} aria-hidden="true" />}
              onClick={onResetUpdateDismissals}
              disabled={!config?.dismissed_update_id && !config?.dismissed_update_until && !config?.skipped_update_version}
            >
              {t("client.diagnostics.resetDismissals")}
            </Button>
          </div>
          {config?.skipped_update_version ? (
            <div style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
              {t("client.diagnostics.skippedVersion")}: {config.skipped_update_version}
            </div>
          ) : null}
        </DiagSection>

        {onOpenLogFile ? (
          <DiagSection title={t("client.diagnostics.sectionLog")}>
            <Button
              size="sm"
              variant="ghost"
              leadingIcon={<FileText size={14} aria-hidden="true" />}
              onClick={onOpenLogFile}
            >
              {t("client.diagnostics.openLogFile")}
            </Button>
          </DiagSection>
        ) : null}
      </div>
    </Dialog>
  );
}

function DiagSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ display: "grid", gap: 8 }}>
      <h3 style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--primary)" }}>
        {title}
      </h3>
      <div style={{ display: "grid", gap: 6 }}>{children}</div>
    </section>
  );
}

function VerboseDiskLoggingRow({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 8, fontSize: "0.86rem" }}>
      <span style={{ color: "var(--muted)" }}>{t("client.diagnostics.verboseLogging")}</span>
      <label
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          color: "var(--text)",
          cursor: "pointer",
        }}
      >
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          style={{ marginTop: 3, accentColor: "var(--primary)" }}
        />
        <span style={{ display: "grid", gap: 2 }}>
          <span>{t("client.diagnostics.verboseLoggingDesc")}</span>
          <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
            {t("client.diagnostics.verboseLoggingHint")}
          </span>
        </span>
      </label>
    </div>
  );
}

function DiagRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 8, fontSize: "0.86rem" }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span
        style={{
          color: "var(--text)",
          wordBreak: "break-all",
          fontFamily: mono ? '"Consolas", "D2Coding", monospace' : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}
