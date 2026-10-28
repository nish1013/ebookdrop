import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactNode } from "react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { ZodType } from "zod";
import { Alert } from "../ui/alert";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import type { Credentials } from "./identity.schema";

export interface CredentialsFormProps {
  title: string;
  description: string;
  submitLabel: string;
  schema: ZodType<Credentials, Credentials>;
  onSubmit: (credentials: Credentials) => Promise<string | null>;
  footer: ReactNode;
}

export function CredentialsForm({ title, description, submitLabel, schema, onSubmit, footer }: CredentialsFormProps) {
  const [refusal, setRefusal] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Credentials>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit(async (credentials) => setRefusal(await onSubmit(credentials)));

  return (
    <main className="grid min-h-screen place-items-center bg-gradient-to-b from-accent to-background px-4">
      <div className="w-full max-w-sm">
        <p className="mb-6 flex items-center justify-center gap-2 text-lg font-semibold">
          <span className="grid size-8 place-items-center rounded-md bg-primary text-xs text-primary-foreground">eb</span>
          ebookdrop
        </p>
        <Card>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <form onSubmit={submit} noValidate>
            <CardContent className="grid gap-4">
              <Label>
                Email
                <Input type="email" autoComplete="email" {...register("email")} />
              </Label>
              {formState.errors.email && <p className="text-sm text-destructive">{formState.errors.email.message}</p>}
              <Label>
                Password
                <Input type="password" {...register("password")} />
              </Label>
              {formState.errors.password && (
                <p className="text-sm text-destructive">{formState.errors.password.message}</p>
              )}
              {refusal && <Alert variant="destructive">{refusal}</Alert>}
              <Button type="submit" className="w-full" disabled={formState.isSubmitting}>
                {submitLabel}
              </Button>
            </CardContent>
          </form>
          <CardFooter className="justify-center text-sm text-muted-foreground">{footer}</CardFooter>
        </Card>
      </div>
    </main>
  );
}
