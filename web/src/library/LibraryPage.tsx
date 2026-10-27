import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";

export function LibraryPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    api.GET("/api/sessions/current").then(({ data }) => {
      if (data) setEmail(data.email);
      else navigate("/sign-in", { replace: true });
    });
  }, [navigate]);

  async function signOut() {
    await api.DELETE("/api/sessions/current");
    navigate("/sign-in", { replace: true });
  }

  if (email === null) return null;

  return (
    <main>
      <header>
        <span>{email}</span>
        <button type="button" onClick={signOut}>
          Sign out
        </button>
      </header>
      <h1>Library</h1>
      <p>Your library is empty</p>
    </main>
  );
}
