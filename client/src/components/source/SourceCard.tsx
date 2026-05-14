import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { probeForValidity, type ValidityState } from "../../lib/path-validity";
import { pickFile, pickFolder, probePath, isTauriRuntime } from "../../tauri";
import type { ClientConfig, ClientType } from "../../types";
import { Badge } from "../primitives/Badge";
import { PathField } from "./PathField";

const CLIENT_LABEL: Record<ClientType, string> = {
  lr2: "LR2",
  beatoraja: "Beatoraja",
};

interface SourceFieldSpec {
  labelKey: string;
  pickKind: string;
  pathKey: keyof ClientConfig;
  required: boolean;
  hintKey: string;
  pickerType?: "file" | "folder";
  validation: "lr2-score" | "lr2-song" | "beatoraja-score-dir" | "beatoraja-songdata" | "beatoraja-songinfo";
}

const LR2_FIELDS: SourceFieldSpec[] = [
  {
    labelKey: "client.source.cards.lr2Score.label",
    pickKind: "lr2-score",
    pathKey: "lr2_db_path",
    required: false,
    hintKey: "client.source.cards.lr2Score.hint",
    pickerType: "file",
    validation: "lr2-score",
  },
  {
    labelKey: "client.source.cards.lr2Song.label",
    pickKind: "lr2-song",
    pathKey: "lr2_song_db_path",
    required: false,
    hintKey: "client.source.cards.lr2Song.hint",
    pickerType: "file",
    validation: "lr2-song",
  },
];

const BEATORAJA_FIELDS: SourceFieldSpec[] = [
  {
    labelKey: "client.source.cards.beatorajaScoreFolder.label",
    pickKind: "bea-dir",
    pathKey: "beatoraja_db_dir",
    required: false,
    hintKey: "client.source.cards.beatorajaScoreFolder.hint",
    pickerType: "folder",
    validation: "beatoraja-score-dir",
  },
  {
    labelKey: "client.source.cards.beatorajaSongData.label",
    pickKind: "bea-songdata",
    pathKey: "beatoraja_songdata_db_path",
    required: false,
    hintKey: "client.source.cards.beatorajaSongData.hint",
    pickerType: "file",
    validation: "beatoraja-songdata",
  },
  {
    labelKey: "client.source.cards.beatorajaSongInfo.label",
    pickKind: "bea-songinfo",
    pathKey: "beatoraja_songinfo_db_path",
    required: false,
    hintKey: "client.source.cards.beatorajaSongInfo.hint",
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
  onPickError?: (message: string) => void;
}

export function SourceCard({
  client,
  config,
  onUpdate,
  onPickError,
}: SourceCardProps) {
  const { t } = useTranslation();
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

  const statusTone: "success" | "warn" | "danger" | "muted" = !hasAllRequired
    ? "warn"
    : hasPathProblems
      ? "danger"
      : "success";
  const statusLabel = !hasAllRequired
    ? t("client.source.status.missing")
    : hasPathProblems
      ? t("client.source.status.invalid")
      : t("client.source.status.ready");

  const clientLabel = CLIENT_LABEL[client];

  const handleFieldDrop = useCallback((spec: SourceFieldSpec, hint: string) => {
    onUpdate({ [spec.pathKey]: hint } as Partial<ClientConfig>);
  }, [onUpdate]);

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
        if (field) {
          handleFieldDrop(field, path);
        }
        // Drop on the whole card without a specific target field is ignored.
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
  }, [fields, getDropKeyFromPosition, handleFieldDrop, onPickError]);

  async function handleBrowse(spec: SourceFieldSpec) {
    try {
      const result =
        spec.pickerType === "folder"
          ? await pickFolder(spec.pickKind)
          : await pickFile(spec.pickKind);
      if (!result) return;
      onUpdate({ [spec.pathKey]: result } as Partial<ClientConfig>);
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
        // Drop on the whole card without a specific target field is ignored.
      }}
    >
      <header className="source-card-hd">
        <div className="source-card-title">
          {clientLabel}
        </div>
        <Badge tone={statusTone}>{statusLabel}</Badge>
      </header>

      <div className="source-card-paths">
        {fields.map((field) => (
          <PathField
            key={field.pathKey as string}
            label={t(field.labelKey)}
            value={(config[field.pathKey] as string) ?? ""}
            inputName={`ojik-${field.pathKey as string}`}
            onChange={(next) =>
              onUpdate({ [field.pathKey]: next || null } as Partial<ClientConfig>)
            }
            onBrowse={() => handleBrowse(field)}
            onDrop={(hint) => handleFieldDrop(field, hint)}
            dropTargetKey={field.pathKey as string}
            dropOver={activeDropKey === field.pathKey}
            required={field.required}
            hint={t(field.hintKey)}
            validity={validityMap[field.pathKey as string] ?? null}
          />
        ))}
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
      if (base.kind !== "file") return invalid(base, "client.source.validation.fileRequired");
      if (!name.endsWith(".db")) return invalid(base, "client.source.validation.dbFileRequired");
      return base;
    case "lr2-song":
      if (base.kind !== "file") return invalid(base, "client.source.validation.fileRequired");
      if (name !== "song.db") return invalid(base, "client.source.validation.exactFileNameRequired:song.db");
      return base;
    case "beatoraja-score-dir": {
      if (base.kind !== "dir") return invalid(base, "client.source.validation.dirRequired");
      const score = await probePath(joinPath(base.path, "score.db"));
      if (!score?.exists || score.kind !== "file") {
        return invalid(base, "client.source.validation.missingScoreDb");
      }
      const scorelog = await probePath(joinPath(base.path, "scorelog.db"));
      if (!scorelog?.exists || scorelog.kind !== "file") {
        return invalid(base, "client.source.validation.missingScoreLogDb");
      }
      return base;
    }
    case "beatoraja-songdata":
      if (base.kind !== "file") return invalid(base, "client.source.validation.fileRequired");
      if (name !== "songdata.db") return invalid(base, "client.source.validation.exactFileNameRequired:songdata.db");
      return base;
    case "beatoraja-songinfo":
      if (base.kind !== "file") return invalid(base, "client.source.validation.fileRequired");
      if (name !== "songinfo.db") return invalid(base, "client.source.validation.exactFileNameRequired:songinfo.db");
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
