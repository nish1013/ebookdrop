export const PASSWORD_MIN_LENGTH = 12;

const MESSAGES: Record<string, string> = {
  email_taken: "This email already has an account",
  invalid_email: "Enter a valid email address",
  wrong_email_or_password: "Email or password is wrong",
  too_many_attempts: "Too many attempts. Try again later.",
};

export function messageFor(error: object): string {
  const code = "code" in error && typeof error.code === "string" ? error.code : "";
  return MESSAGES[code] ?? "Something went wrong. Try again.";
}
