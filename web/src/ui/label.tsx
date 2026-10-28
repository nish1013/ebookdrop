import type { LabelHTMLAttributes } from "react";
import { cn } from "./ui.util";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("grid gap-2 text-sm font-medium leading-none", className)} {...props} />;
}
