import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { messageFor } from "./identity.constants";
import type { Credentials } from "./identity.schema";
import { credentialsSchema } from "./identity.schema";
import { CredentialsForm } from "./CredentialsForm";

export function SignInPage() {
  const navigate = useNavigate();

  async function signIn(credentials: Credentials): Promise<string | null> {
    const { error } = await api.POST("/api/sessions", { body: credentials });
    if (error) return messageFor(error);
    navigate("/library");
    return null;
  }

  return (
    <CredentialsForm
      title="Sign in"
      description="Welcome back. Your library is waiting."
      submitLabel="Sign in"
      schema={credentialsSchema}
      onSubmit={signIn}
      footer={
        <span>
          New here?{" "}
          <Link to="/sign-up" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign up
          </Link>
        </span>
      }
    />
  );
}
