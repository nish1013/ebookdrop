import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api/client";
import { Alert } from "../ui/alert";
import { buttonVariants } from "../ui/button";
import { PageShell } from "../ui/PageShell";
import { READER_MESSAGES, readerState, readerUrl } from "./reader.constants";
import type { ReaderState } from "./reader.types";

export function ReaderPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const frame = useRef<HTMLIFrameElement>(null);
  const [state, setState] = useState<ReaderState>("opening");

  useEffect(() => {
    function receive(event: MessageEvent<unknown>) {
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow) return;
      const next = readerState(event.data);
      if (next === null) return;
      setState(next);
      if (next === "failed") api.POST("/api/books/{book_id}/open-failures", { params: { path: { book_id: bookId } } });
      if (next === "signed_out") navigate("/sign-in", { replace: true });
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [bookId, navigate]);

  const message = READER_MESSAGES[state];

  return (
    <PageShell
      actions={
        <Link to="/library" className={buttonVariants({ variant: "ghost", size: "sm" })}>
          Library
        </Link>
      }
    >
      {message && <Alert>{message}</Alert>}
      <iframe
        ref={frame}
        title="Book"
        src={readerUrl(bookId)}
        hidden={message !== undefined}
        className="h-[78vh] w-full rounded-xl border bg-card shadow-sm"
      />
    </PageShell>
  );
}
