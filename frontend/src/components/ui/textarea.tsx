import * as React from "react";
import { cn } from "@/lib/utils";
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...p }, r) => (
  <textarea
    ref={r}
    className={cn(
      "flex min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring",
      className,
    )}
    {...p}
  />
));
Textarea.displayName = "Textarea";
