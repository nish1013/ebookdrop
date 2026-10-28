import { useState } from "react";
import { Link } from "react-router";
import type { BookOut } from "./library.constants";
import { bookAnchor, FAILURE_MESSAGES, STATUS_LABELS } from "./library.constants";

export interface BookListProps {
  books: BookOut[];
  onDelete: (book: BookOut) => Promise<void>;
}

export function BookList({ books, onDelete }: BookListProps) {
  const [confirming, setConfirming] = useState<string | null>(null);

  if (books.length === 0) return <p>Your library is empty</p>;

  return (
    <ul>
      {books.map((book) => (
        <li key={book.id} id={bookAnchor(book.id)}>
          {book.cover_url ? (
            <img src={book.cover_url} alt={`Cover of ${book.title}`} width={60} />
          ) : (
            <div role="img" aria-label={`Cover of ${book.title}`} className="plain-cover">
              {book.title}
            </div>
          )}
          <span>{book.title}</span>
          {book.author && <span>{book.author}</span>}
          <span>{STATUS_LABELS[book.status]}</span>
          {book.failure && <span>{FAILURE_MESSAGES[book.failure]}</span>}
          {book.status === "ready" && (
            <Link to={`/books/${book.id}`} aria-label={`Read ${book.title}`}>
              Read
            </Link>
          )}
          {confirming === book.id ? (
            <div role="group" aria-label={`Delete ${book.title}?`}>
              <span>Delete {book.title}? This cannot be undone.</span>
              <button type="button" onClick={() => onDelete(book).then(() => setConfirming(null))}>
                Delete for good
              </button>
              <button type="button" onClick={() => setConfirming(null)}>
                Keep
              </button>
            </div>
          ) : (
            <button type="button" aria-label={`Delete ${book.title}`} onClick={() => setConfirming(book.id)}>
              Delete
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
