import type { TFunction } from "i18next";

const WORSE_ERROR_TO_FIELD_KEY: Record<string, string> = {
  clear_type_worse: "common.fields.clear",
  min_bp_worse: "common.fields.bp",
  rank_worse: "common.fields.rank",
  rate_worse: "common.fields.rate",
};

export function formatGoalValidationErrors(errors: string[], t: TFunction): string {
  const worseFields = errors
    .map((code) => WORSE_ERROR_TO_FIELD_KEY[code])
    .filter((key): key is string => Boolean(key))
    .map((key) => t(key));
  const otherErrors = errors.filter((code) => !WORSE_ERROR_TO_FIELD_KEY[code]);
  const messages: string[] = [];

  if (worseFields.length > 0) {
    messages.push(t("goals.setup.errors.conditions_worse", { columns: worseFields.join(", ") }));
  }
  messages.push(...otherErrors.map((code) => t(`goals.setup.errors.${code}`)));

  return messages.join(" ");
}
