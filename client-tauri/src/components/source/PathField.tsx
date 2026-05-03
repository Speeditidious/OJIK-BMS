import { AlertTriangle, CheckCircle2, FolderOpen, HelpCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

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
  placeholder = "경로를 입력하거나 파일을 드래그&드롭 하세요",
  required,
  hint,
  validity: externalValidity,
}: PathFieldProps) {
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
          {required ? <span className="field-required"> · 필수</span> : null}
        </span>
        <ValidityChip validity={validity} />
      </span>
      {hint ? <span className="field-hint">{hint}</span> : null}
      <div className="field-row">
        <span className="field-input-wrap">
          <input
            type="text"
            value={value ?? ""}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
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
          aria-label={`${label} 경로 선택`}
          disabled={!onBrowse}
          title="경로 선택"
        >
          <FolderOpen size={15} aria-hidden="true" />
        </Button>
      </div>
    </label>
  );
}

function ValidityChip({ validity }: { validity: ValidityState | null }) {
  if (!validity) return null;
  switch (validity.validity) {
    case "valid":
      return (
        <span style={{ color: "var(--success)", fontSize: "0.74rem" }}>
          {validity.kind === "dir" ? "폴더 확인됨" : "파일 확인됨"}
        </span>
      );
    case "invalid":
      return (
        <span style={{ color: "var(--danger)", fontSize: "0.74rem" }}>
          {validity.reason ?? "유효하지 않은 경로"}
        </span>
      );
    case "missing":
      return <span style={{ color: "var(--warning)", fontSize: "0.74rem" }}>파일 없음</span>;
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
