import { useState } from "react";
import { Link } from "react-router";
import { Badge } from "../ui/badge";
import { Button, buttonVariants } from "../ui/button";
import { Card } from "../ui/card";
import type { BookOut } from "./library.constants";
import { bookAnchor, FAILURE_MESSAGES, STATUS_BADGES, STATUS_LABELS } from "./library.constants";

export interface BookListProps {
  books: BookOut[];
  onDelete: (book: BookOut) => Promise<void>;
}

export function BookList({ books, onDelete }: BookListProps) {
  const [confirming, setConfirming] = useState<string | null>(null);

  if (books.length === 0)
    return (
      <Card className="grid place-items-center gap-1 px-6 py-16 text-center">
        <p className="font-medium">Your library is empty</p>
        <p className="text-sm text-muted-foreground">Upload an EPUB or PDF to start reading.</p>
      </Card>
    );

  return (
    <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
      {books.map((book) => (
        <li key={book.id} id={bookAnchor(book.id)} className="target:ring-2 target:ring-ring rounded-xl">
          <Card className="flex h-full flex-col overflow-hidden">
            {book.cover_url ? (
              <img
                src={book.cover_url}
                alt={`Cover of ${book.title}`}
                className="aspect-[2/3] w-full bg-muted object-cover"
              />
            ) : (
              <div
                role="img"
                aria-label={`Cover of ${book.title}`}
                className="grid aspect-[2/3] w-full place-items-center bg-gradient-to-br from-primary to-indigo-400 p-4 text-center font-serif text-lg text-primary-foreground"
              >
                {book.title}
              </div>
            )}
            <div className="flex flex-1 flex-col gap-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="line-clamp-2 font-medium leading-snug">{book.title}</span>
                <Badge variant={STATUS_BADGES[book.status]}>{STATUS_LABELS[book.status]}</Badge>
              </div>
              {book.author && <span className="text-sm text-muted-foreground">{book.author}</span>}
              {book.failure && <span className="text-sm text-destructive">{FAILURE_MESSAGES[book.failure]}</span>}
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
                {book.status === "ready" && (
                  <Link to={`/books/${book.id}`} aria-label={`Read ${book.title}`} className={buttonVariants({ size: "sm" })}>
                    Read
                  </Link>
                )}
                {confirming === book.id ? (
                  <div role="group" aria-label={`Delete ${book.title}?`} className="grid w-full gap-2">
                    <span className="text-sm">Delete {book.title}? This cannot be undone.</span>
                    <div className="flex gap-2">
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => onDelete(book).then(() => setConfirming(null))}
                      >
                        Delete for good
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setConfirming(null)}>
                        Keep
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button variant="ghost" size="sm" aria-label={`Delete ${book.title}`} onClick={() => setConfirming(book.id)}>
                    Delete
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </li>
      ))}
    </ul>
  );
}
