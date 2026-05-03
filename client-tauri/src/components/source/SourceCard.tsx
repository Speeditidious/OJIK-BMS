import { Database, Download } from "lucide-react";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useCallback, useEffect, useRef, useState } from "react";

import { probeForValidity, type ValidityState } from "../../lib/path-validity";
import { detectClientPaths, pickFile, pickFolder, probePath } from "../../tauri";
import { isTauriRuntime } from "../../tauri";
import type { ClientConfig, ClientType } from "../../types";
import { Badge } from "../primitives/Badge";
import { Button } from "../primitives/Button";
import { PathField } from "./PathField";
import {
  mergeSuggestionPatch,
  suggestPathsFromHint,
  type DropClient,
  type SuggestedPaths,
} from "./source-detect";

const CLIENT_LABEL: Record<ClientType, string> = {
  lr2: "LR2",
  beatoraja: "Beatoraja",
};

interface SourceFieldSpec {
  label: string;
  pickKind: string;
  pathKey: keyof ClientConfig;
  required: boolean;
  hint?: string;
  pickerType?: "file" | "folder";
  validation: "lr2-score" | "lr2-song" | "beatoraja-score-dir" | "beatoraja-songdata" | "beatoraja-songinfo";
}

const LR2_FIELDS: SourceFieldSpec[] = [
  {
    label: "score.db",
    pickKind: "lr2-score",
    pathKey: "lr2_db_path",
    required: true,
    hint: "LR2files/Database/Score 경로에 있는 {username}.db 파일을 업로드 해주세요. 일반적으로 용량이 제일 큰 파일입니다.",
    pickerType: "file",
    validation: "lr2-score",
  },
  {
    label: "song.db",
    pickKind: "lr2-song",
    pathKey: "lr2_song_db_path",
    required: false,
    hint: "LR2files/Database 경로에 있는 song.db 파일을 업로드 해주세요.",
    pickerType: "file",
    validation: "lr2-song",
  },
];

const BEATORAJA_FIELDS: SourceFieldSpec[] = [
  {
    label: "플레이 기록 DB 폴더",
    pickKind: "bea-dir",
    pathKey: "beatoraja_db_dir",
    required: true,
    hint: "score.db / scorelog.db가 들어 있는 폴더를 업로드 해주세요. 일반적으로 player/player1 폴더입니다.",
    pickerType: "folder",
    validation: "beatoraja-score-dir",
  },
  {
    label: "songdata.db",
    pickKind: "bea-songdata",
    pathKey: "beatoraja_songdata_db_path",
    required: false,
    hint: "beatoraja 최상위 폴더에 있는 songdata.db 파일을 업로드 해주세요.",
    pickerType: "file",
    validation: "beatoraja-songdata",
  },
  {
    label: "songinfo.db",
    pickKind: "bea-songinfo",
    pathKey: "beatoraja_songinfo_db_path",
    required: false,
    hint: "beatoraja 최상위 폴더에 있는 songinfo.db 파일을 업로드 해주세요.",
    pickerType: "file",
    validation: "beatoraja-songinfo",
  },
];

const FIELDS: Record<ClientType, SourceFieldSpec[]> = {
  lr2: LR2_FIELDS,
  beatoraja: BEATORAJA_FIELDS,
};

export interface SourceCardProps {
  client: ClientType;
  config: ClientConfig;
  onUpdate: (patch: Partial<ClientConfig>) => void;
  onQuickSync: () => void;
  onFullSync: () => void;
  syncDisabled: boolean;
  syncDisabledReason?: string;
  onPickError?: (message: string) => void;
}

export function SourceCard({
  client,
  config,
  onUpdate,
  onQuickSync,
  onFullSync,
  syncDisabled,
  syncDisabledReason,
  onPickError,
}: SourceCardProps) {
  const fields = FIELDS[client];
  const [isDropOver, setIsDropOver] = useState(false);
  const [activeDropKey, setActiveDropKey] = useState<string | null>(null);
  const [validityMap, setValidityMap] = useState<Record<string, ValidityState | null>>({});
  const cardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      fields.map(async (f) => {
        const v = await validateSourcePath(config[f.pathKey] as string | null, f);
        return [f.pathKey as string, v] as const;
      }),
    ).then((entries) => {
      if (cancelled) return;
      setValidityMap(Object.fromEntries(entries));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, ...fields.map((f) => config[f.pathKey])]);

  const requiredKeys = fields.filter((f) => f.required).map((f) => f.pathKey);
  const hasAllRequired = requiredKeys.every((k) => Boolean(config[k]));
  const configuredKeys = fields.filter((f) => Boolean(config[f.pathKey])).map((f) => f.pathKey);
  const hasPathProblems = configuredKeys.some(
    (k) => {
      const validity = validityMap[k as string]?.validity;
      return validity === "missing" || validity === "invalid";
    },
  );

  const status: { tone: "success" | "warn" | "danger" | "muted"; label: string } = !hasAllRequired
    ? { tone: "warn", label: "경로 누락" }
    : hasPathProblems
      ? { tone: "danger", label: "경로 오류" }
      : { tone: "success", label: "준비됨" };
  const clientLabel = CLIENT_LABEL[client];

  const applySuggestion = useCallback((suggestion: SuggestedPaths, overwrite = false) => {
    const patch = mergeSuggestionPatch(config, suggestion, { overwrite });
    if (Object.keys(patch).length > 0) {
      onUpdate(patch);
    }
  }, [config, onUpdate]);

  const handleDrop = useCallback(async (hint: string) => {
    const suggestion = suggestPathsFromHint(client as DropClient, hint);
    applySuggestion(suggestion);
    const detected = await detectClientPaths(client, hint);
    if (detected) applySuggestion(detected);
  }, [applySuggestion, client]);

  const handleFieldDrop = useCallback(async (spec: SourceFieldSpec, hint: string) => {
    onUpdate({ [spec.pathKey]: hint } as Partial<ClientConfig>);
    await handleDrop(hint);
  }, [handleDrop, onUpdate]);

  const getDropKeyFromPosition = useCallback((position: { x: number; y: number }): string | null => {
    const ratio = window.devicePixelRatio || 1;
    const element = document.elementFromPoint(position.x / ratio, position.y / ratio);
    if (!element || !cardRef.current?.contains(element)) return null;
    const target = element.closest<HTMLElement>("[data-path-drop-key]");
    return target?.dataset.pathDropKey ?? null;
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    let unlisten: (() => void) | null = null;
    let cancelled = false;

    getCurrentWebview()
      .onDragDropEvent((event) => {
        const payload = event.payload;
        if (payload.type === "leave") {
          setIsDropOver(false);
          setActiveDropKey(null);
          return;
        }
        if (payload.type === "enter" || payload.type === "over") {
          const key = getDropKeyFromPosition(payload.position);
          const overCard = Boolean(key) || Boolean(cardRef.current?.contains(document.elementFromPoint(
            payload.position.x / (window.devicePixelRatio || 1),
            payload.position.y / (window.devicePixelRatio || 1),
          )));
          setIsDropOver(overCard);
          setActiveDropKey(key);
          return;
        }
        const [path] = payload.paths;
        if (!path) return;
        const key = getDropKeyFromPosition(payload.position);
        setIsDropOver(false);
        setActiveDropKey(null);
        if (!cardRef.current?.contains(document.elementFromPoint(
          payload.position.x / (window.devicePixelRatio || 1),
          payload.position.y / (window.devicePixelRatio || 1),
        ))) {
          return;
        }
        const field = fields.find((item) => item.pathKey === key);
        void (field ? handleFieldDrop(field, path) : handleDrop(path));
      })
      .then((nextUnlisten) => {
        if (cancelled) {
          nextUnlisten();
        } else {
          unlisten = nextUnlisten;
        }
      })
      .catch((err) => {
        onPickError?.(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
      unlisten?.();
    };
    // Tauri drop events need the latest config/fields so suggestions do not overwrite freshly typed values.
  }, [fields, getDropKeyFromPosition, handleDrop, handleFieldDrop, onPickError]);

  async function handleBrowse(spec: SourceFieldSpec) {
    try {
      const result =
        spec.pickerType === "folder"
          ? await pickFolder(spec.pickKind)
          : await pickFile(spec.pickKind);
      if (!result) return;
      const patch: Partial<ClientConfig> = { [spec.pathKey]: result } as Partial<ClientConfig>;
      onUpdate(patch);
      // After picking one, suggest sibling paths.
      const suggestion = suggestPathsFromHint(client as DropClient, result);
      applySuggestion(suggestion);
      const detected = await detectClientPaths(client, result);
      if (detected) applySuggestion(detected);
    } catch (err) {
      onPickError?.(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <article
      ref={cardRef}
      className={`source-card${isDropOver ? " is-drop-over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDropOver(true);
      }}
      onDragLeave={() => setIsDropOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDropOver(false);
        const file = e.dataTransfer.files?.[0] as (File & { path?: string }) | undefined;
        if (file?.path) {
          void handleDrop(String(file.path));
          return;
        }
        const text = e.dataTransfer.getData("text/plain");
        if (text) void handleDrop(text);
      }}
    >
      <header className="source-card-hd">
        <div className="source-card-title">
          {clientLabel}
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </header>

      <div className="source-card-paths">
        {fields.map((field) => (
          <PathField
            key={field.pathKey as string}
            label={field.label}
            value={(config[field.pathKey] as string) ?? ""}
            onChange={(next) =>
              onUpdate({ [field.pathKey]: next || null } as Partial<ClientConfig>)
            }
            onBrowse={() => handleBrowse(field)}
            onDrop={(hint) => handleFieldDrop(field, hint)}
            dropTargetKey={field.pathKey as string}
            dropOver={activeDropKey === field.pathKey}
            required={field.required}
            hint={field.hint}
            validity={validityMap[field.pathKey as string] ?? null}
          />
        ))}
      </div>

      <div className="source-card-actions">
        <Button
          variant="primary"
          leadingIcon={<Database size={15} aria-hidden="true" />}
          onClick={onQuickSync}
          disabled={syncDisabled || !hasAllRequired}
          title={syncDisabledReason}
        >
          {clientLabel} 빠른 동기화
        </Button>
        <Button
          variant="accent"
          leadingIcon={<Download size={15} aria-hidden="true" />}
          onClick={onFullSync}
          disabled={syncDisabled || !hasAllRequired}
          title={syncDisabledReason}
        >
          {clientLabel} 전체 동기화
        </Button>
      </div>
    </article>
  );
}

async function validateSourcePath(path: string | null, spec: SourceFieldSpec): Promise<ValidityState> {
  const base = await probeForValidity(path);
  if (base.validity !== "valid") return base;

  const name = basename(base.path).toLowerCase();
  switch (spec.validation) {
    case "lr2-score":
      if (base.kind !== "file") return invalid(base, "파일을 선택해 주세요");
      if (!name.endsWith(".db")) return invalid(base, ".db 파일이어야 합니다");
      return base;
    case "lr2-song":
      if (base.kind !== "file") return invalid(base, "파일을 선택해 주세요");
      if (name !== "song.db") return invalid(base, "파일명이 song.db여야 합니다");
      return base;
    case "beatoraja-score-dir": {
      if (base.kind !== "dir") return invalid(base, "폴더를 선택해 주세요");
      const score = await probePath(joinPath(base.path, "score.db"));
      if (!score?.exists || score.kind !== "file") {
        return invalid(base, "폴더 안에 score.db가 없습니다");
      }
      const scorelog = await probePath(joinPath(base.path, "scorelog.db"));
      if (!scorelog?.exists || scorelog.kind !== "file") {
        return invalid(base, "폴더 안에 scorelog.db가 없습니다");
      }
      return base;
    }
    case "beatoraja-songdata":
      if (base.kind !== "file") return invalid(base, "파일을 선택해 주세요");
      if (name !== "songdata.db") return invalid(base, "파일명이 songdata.db여야 합니다");
      return base;
    case "beatoraja-songinfo":
      if (base.kind !== "file") return invalid(base, "파일을 선택해 주세요");
      if (name !== "songinfo.db") return invalid(base, "파일명이 songinfo.db여야 합니다");
      return base;
    default:
      return base;
  }
}

function invalid(base: ValidityState, reason: string): ValidityState {
  return { ...base, validity: "invalid", reason };
}

function basename(path: string): string {
  const trimmed = path.replace(/[\\/]+$/, "");
  const parts = trimmed.split(/[\\/]/);
  return parts[parts.length - 1] ?? trimmed;
}

function joinPath(dir: string, name: string): string {
  const sep = dir.includes("\\") ? "\\" : "/";
  return `${dir.replace(/[\\/]+$/, "")}${sep}${name}`;
}
