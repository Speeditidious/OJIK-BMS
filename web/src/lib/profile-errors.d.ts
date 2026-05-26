export declare const PROFILE_ERROR_CODES: {
  usernameAlreadyExists: "USERNAME_ALREADY_EXISTS";
};

export function getProfileSaveErrorMessage(
  err: unknown,
  t: (key: string) => string,
): string;
