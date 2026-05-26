export const PROFILE_ERROR_CODES = {
  usernameAlreadyExists: "USERNAME_ALREADY_EXISTS",
};

/**
 * Return the localized profile save error message for known API error codes.
 *
 * @param {unknown} err
 * @param {(key: string) => string} t
 * @returns {string}
 */
export function getProfileSaveErrorMessage(err, t) {
  const message = err instanceof Error ? err.message : "";
  if (message === PROFILE_ERROR_CODES.usernameAlreadyExists) {
    return t("settings.profile.usernameAlreadyExists");
  }
  return message || t("settings.profile.saveFailed");
}
