import type { BookOut } from "./library.constants";
import { bookAnchor, STATUS_LABELS } from "./library.constants";

export interface BookListProps {
  books: BookOut[];
}

export function BookList({ books }: BookListProps) {
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
        </li>
      ))}
    </ul>
  );
}
