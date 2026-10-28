import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { BookList } from "./BookList";
import type { BookOut } from "./library.constants";
import { REFRESH_MS } from "./library.constants";
import { Button, buttonVariants } from "../ui/button";
import { PageShell } from "../ui/PageShell";
import { UploadForm } from "./UploadForm";

export function LibraryPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState<string | null>(null);
  const [books, setBooks] = useState<BookOut[] | null>(null);

  const loadBooks = useCallback(async () => {
    const { data } = await api.GET("/api/books");
    if (data) setBooks(data);
    else navigate("/sign-in", { replace: true });
  }, [navigate]);

  useEffect(() => {
    api.GET("/api/sessions/current").then(({ data }) => {
      if (data) {
        setEmail(data.email);
        loadBooks();
      } else navigate("/sign-in", { replace: true });
    });
  }, [navigate, loadBooks]);

  const processing = books?.some((book) => book.status === "processing") ?? false;

  useEffect(() => {
    if (!processing) return;
    const timer = setTimeout(loadBooks, REFRESH_MS);
    return () => clearTimeout(timer);
  }, [processing, books, loadBooks]);

  async function deleteBook(book: BookOut) {
    await api.DELETE("/api/books/{book_id}", { params: { path: { book_id: book.id } } });
    await loadBooks();
  }

  async function signOut() {
    await api.DELETE("/api/sessions/current");
    navigate("/sign-in", { replace: true });
  }

  if (email === null || books === null) return null;

  return (
    <PageShell
      actions={
        <>
          <span className="hidden text-muted-foreground sm:inline">{email}</span>
          <Link to="/account" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            Account
          </Link>
          <Button variant="outline" size="sm" onClick={signOut}>
            Sign out
          </Button>
        </>
      }
    >
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
          <p className="text-sm text-muted-foreground">
            {books.length === 1 ? "1 book" : `${books.length} books`}. EPUB and PDF, up to 50 MB each.
          </p>
        </div>
      </div>
      <UploadForm onUploaded={loadBooks} />
      <BookList books={books} onDelete={deleteBook} />
    </PageShell>
  );
}
