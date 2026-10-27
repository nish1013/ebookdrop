import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { messageFor } from "./identity.constants";
import type { Credentials } from "./identity.schema";
import { signUpSchema } from "./identity.schema";
import { CredentialsForm } from "./CredentialsForm";

export function SignUpPage() {
  const navigate = useNavigate();

  async function signUp(credentials: Credentials): Promise<string | null> {
    const created = await api.POST("/api/accounts", { body: credentials });
    if (created.error) return messageFor(created.error);
    const signedIn = await api.POST("/api/sessions", { body: credentials });
    if (signedIn.error) return messageFor(signedIn.error);
    navigate("/library");
    return null;
  }

  return (
    <>
      <CredentialsForm title="Sign up" submitLabel="Sign up" schema={signUpSchema} onSubmit={signUp} />
      <p>
        Have an account? <Link to="/sign-in">Sign in</Link>
      </p>
    </>
  );
}
