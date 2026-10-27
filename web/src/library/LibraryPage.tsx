import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { BookList } from "./BookList";
import type { BookOut } from "./library.constants";
import { REFRESH_MS } from "./library.constants";
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
    <main>
      <header>
        <span>{email}</span>
        <Link to="/account">Account</Link>
        <button type="button" onClick={signOut}>
          Sign out
        </button>
      </header>
      <h1>Library</h1>
      <UploadForm onUploaded={loadBooks} />
      <BookList books={books} onDelete={deleteBook} />
    </main>
  );
}
