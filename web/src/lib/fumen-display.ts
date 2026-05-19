import { decodeFumenDisplayText as coreDecodeFumenDisplayText } from "./fumen-display-core.mjs";

export function decodeFumenDisplayText(value: string): string {
  return coreDecodeFumenDisplayText(value) as string;
}

export function fumenTitleText(value: string | null | undefined, fallback = "(Untitled)"): string {
  const text = decodeFumenDisplayText(value ?? "");
  return text || fallback;
}

export function fumenArtistText(value: string | null | undefined): string {
  return decodeFumenDisplayText(value ?? "");
}
