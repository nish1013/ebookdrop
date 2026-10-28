import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { messageFor } from "./identity.constants";

export function AccountPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/sessions/current").then(({ data }) => {
      if (data) setEmail(data.email);
      else navigate("/sign-in", { replace: true });
    });
  }, [navigate]);

  async function deleteAccount() {
    const { error } = await api.DELETE("/api/accounts/me");
    if (error) {
      setRefusal(messageFor(error));
      return;
    }
    navigate("/sign-up", { replace: true });
  }

  if (email === null) return null;

  return (
    <main>
      <Link to="/library">Library</Link>
      <h1>Account</h1>
      <p>{email}</p>
      {refusal && <p role="alert">{refusal}</p>}
      {confirming ? (
        <div role="group" aria-label="Delete your account?">
          <span>Delete your account and every book in it? This cannot be undone.</span>
          <button type="button" onClick={deleteAccount}>
            Delete for good
          </button>
          <button type="button" onClick={() => setConfirming(false)}>
            Keep
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirming(true)}>
          Delete account
        </button>
      )}
    </main>
  );
}
