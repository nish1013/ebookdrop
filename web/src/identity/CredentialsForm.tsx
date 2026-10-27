import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { ZodType } from "zod";
import type { Credentials } from "./identity.schema";

export interface CredentialsFormProps {
  title: string;
  submitLabel: string;
  schema: ZodType<Credentials, Credentials>;
  onSubmit: (credentials: Credentials) => Promise<string | null>;
}

export function CredentialsForm({ title, submitLabel, schema, onSubmit }: CredentialsFormProps) {
  const [refusal, setRefusal] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Credentials>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit(async (credentials) => setRefusal(await onSubmit(credentials)));

  return (
    <main>
      <h1>{title}</h1>
      <form onSubmit={submit} noValidate>
        <label>
          Email
          <input type="email" autoComplete="email" {...register("email")} />
        </label>
        {formState.errors.email && <p>{formState.errors.email.message}</p>}
        <label>
          Password
          <input type="password" {...register("password")} />
        </label>
        {formState.errors.password && <p>{formState.errors.password.message}</p>}
        {refusal && <p role="alert">{refusal}</p>}
        <button type="submit" disabled={formState.isSubmitting}>
          {submitLabel}
        </button>
      </form>
    </main>
  );
}
