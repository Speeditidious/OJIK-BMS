import { AlertTriangle, CheckCircle2, FolderOpen, HelpCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { probeForValidity, type ValidityState } from "../../lib/path-validity";
import { Button } from "../primitives/Button";

export interface PathFieldProps {
  label: string;
  value: string | null;
  onChange: (next: string) => void;
  onBrowse?: () => void;
  onDrop?: (droppedPath: string) => void;
  dropTargetKey?: string;
  dropOver?: boolean;
  placeholder?: string;
  inputName?: string;
  required?: boolean;
  hint?: string;
  validity?: ValidityState | null;
}

export function PathField({
  label,
  value,
  onChange,
  onBrowse,
  onDrop,
  dropTargetKey,
  dropOver,
  placeholder,
  inputName,
  required,
  hint,
  validity: externalValidity,
}: PathFieldProps) {
  const { t } = useTranslation();
  const [autoValidity, setAutoValidity] = useState<ValidityState | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  useEffect(() => {
    if (externalValidity) {
      setAutoValidity(externalValidity);
      return;
    }
    let cancelled = false;
    probeForValidity(value).then((next) => {
      if (!cancelled) setAutoValidity(next);
    });
    return () => {
      cancelled = true;
    };
  }, [value, externalValidity]);

  const validity = externalValidity ?? autoValidity;
  const resolvedPlaceholder = placeholder ?? t("client.source.pathField.placeholder");

  return (
    <label
      className={`field${isDragOver || dropOver ? " is-drop-over" : ""}`}
      data-path-drop-key={dropTargetKey}
      onDragOver={(e) => {
        if (onDrop) {
          e.preventDefault();
          setIsDragOver(true);
        }
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        if (!onDrop) return;
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files?.[0] as (File & { path?: string }) | undefined;
        if (file?.path) {
          onDrop(String(file.path));
          return;
        }
        const text = e.dataTransfer.getData("text/plain");
        if (text) onDrop(text);
      }}
    >
      <span className="field-label">
        <span>
          {label}
          {required ? <span className="field-required"> · {t("client.source.pathField.required")}</span> : null}
        </span>
        <ValidityChip validity={validity} />
      </span>
      {hint ? <span className="field-hint">{hint}</span> : null}
      <div className="field-row">
        <span className="field-input-wrap">
          <input
            type="text"
            name={inputName}
            value={value ?? ""}
            placeholder={resolvedPlaceholder}
            onChange={(e) => onChange(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
          />
          <span className="field-validity" aria-hidden="true">
            <ValidityIcon validity={validity} />
          </span>
        </span>
        <Button
          variant="ghost"
          iconOnly
          onClick={onBrowse}
          aria-label={`${label} ${t("client.source.pathField.pickPath")}`}
          disabled={!onBrowse}
          title={t("client.source.pathField.pickPath")}
        >
          <FolderOpen size={15} aria-hidden="true" />
        </Button>
      </div>
    </label>
  );
}

function ValidityChip({ validity }: { validity: ValidityState | null }) {
  const { t } = useTranslation();
  if (!validity) return null;
  switch (validity.validity) {
    case "valid":
      return (
        <span style={{ color: "var(--success)", fontSize: "0.74rem" }}>
          {validity.kind === "dir"
            ? t("client.source.pathField.dirValid")
            : t("client.source.pathField.fileValid")}
        </span>
      );
    case "invalid": {
      // reason may be:
      //  - an i18n key "client.source.validation.fileRequired"
      //  - an i18n key with arg "client.source.validation.exactFileNameRequired:song.db"
      //  - a plain string (legacy fallback)
      let reasonText: string;
      if (validity.reason) {
        if (validity.reason.startsWith("client.")) {
          const colonIdx = validity.reason.indexOf(":");
          if (colonIdx !== -1) {
            const key = validity.reason.slice(0, colonIdx);
            const fileName = validity.reason.slice(colonIdx + 1);
            reasonText = t(key, { fileName });
          } else {
            reasonText = t(validity.reason);
          }
        } else {
          reasonText = validity.reason;
        }
      } else {
        reasonText = t("client.source.pathField.invalidPath");
      }
      return (
        <span style={{ color: "var(--danger)", fontSize: "0.74rem" }}>
          {reasonText}
        </span>
      );
    }
    case "missing":
      return <span style={{ color: "var(--warning)", fontSize: "0.74rem" }}>{t("client.source.pathField.fileMissing")}</span>;
    case "empty":
      return null;
    default:
      return null;
  }
}

function ValidityIcon({ validity }: { validity: ValidityState | null }) {
  if (!validity) return null;
  switch (validity.validity) {
    case "valid":
      return <CheckCircle2 size={15} className="field-validity-success" />;
    case "missing":
      return <AlertTriangle size={15} className="field-validity-warn" />;
    case "invalid":
      return <XCircle size={15} className="field-validity-danger" />;
    case "unknown":
      return <HelpCircle size={15} className="field-validity-muted" />;
    case "empty":
      return null;
    default:
      return <XCircle size={15} className="field-validity-danger" />;
  }
}
