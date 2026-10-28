import type { ReactNode } from "react";
import { Link } from "react-router";

export interface PageShellProps {
  actions?: ReactNode;
  children: ReactNode;
}

export function PageShell({ actions, children }: PageShellProps) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b bg-card/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <Link to="/library" aria-label="ebookdrop home" className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-xs text-primary-foreground">
              eb
            </span>
            ebookdrop
          </Link>
          <div className="flex items-center gap-2 text-sm">{actions}</div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}
