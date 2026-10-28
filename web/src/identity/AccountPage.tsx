import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { Alert } from "../ui/alert";
import { Button, buttonVariants } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { PageShell } from "../ui/PageShell";
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
    <PageShell
      actions={
        <Link to="/library" className={buttonVariants({ variant: "ghost", size: "sm" })}>
          Library
        </Link>
      }
    >
      <div className="mx-auto grid max-w-xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>You are signed in as</CardDescription>
            <p className="font-medium">{email}</p>
          </CardHeader>
        </Card>
        <Card className="border-destructive/40">
          <CardHeader>
            <h2 className="text-lg font-semibold">Delete account</h2>
            <CardDescription>Removes your account, every book in it and all their files.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {refusal && <Alert variant="destructive">{refusal}</Alert>}
            {confirming ? (
              <div role="group" aria-label="Delete your account?" className="grid gap-3">
                <span className="text-sm">Delete your account and every book in it? This cannot be undone.</span>
                <div className="flex gap-2">
                  <Button variant="destructive" onClick={deleteAccount}>
                    Delete for good
                  </Button>
                  <Button variant="outline" onClick={() => setConfirming(false)}>
                    Keep
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="destructive" className="w-fit" onClick={() => setConfirming(true)}>
                Delete account
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
