export declare const JUDGMENT_STYLE: Record<string, { color: string }>;

export declare const ARRANGEMENT_REASON_I18N_KEY: Record<string, string>;

export declare function arrangementOptionLabel(optionLabel: string | null): string;

export declare function arrangementColumnLabel(
  parsedArrangementName: string | null,
  arrangement: { option_label?: string | null } | null | undefined,
): string | null;

export declare function laneIsWhiteKey(keymode: number, laneIndex: number): boolean;
