import { z } from "zod";
import { PASSWORD_MIN_LENGTH } from "./identity.constants";

export const credentialsSchema = z.object({
  email: z.string().min(1, "Enter your email"),
  password: z.string().min(1, "Enter your password"),
});

export const signUpSchema = credentialsSchema.extend({
  password: z
    .string()
    .min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters`),
});

export type Credentials = z.infer<typeof credentialsSchema>;
