import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api/client";
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
    <main>
      <nav>
        <Link to="/library">Library</Link>
      </nav>
      {message && <p role="alert">{message}</p>}
      <iframe
        ref={frame}
        title="Book"
        src={readerUrl(bookId)}
        hidden={message !== undefined}
        style={{ width: "100%", height: "85vh", border: 0 }}
      />
    </main>
  );
}
