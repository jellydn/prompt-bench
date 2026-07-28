import * as React from "react";
import { cn } from "@/lib/utils";
const make = (tag: "div" | "h2" | "h3" | "p", base: string) =>
  React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
    ({ className, ...p }, r) =>
      React.createElement(tag, {
        ref: r,
        className: cn(base, className),
        ...p,
      }),
  );
export const Card = make(
  "div",
  "rounded-xl border bg-card text-card-foreground shadow-sm",
);
export const CardHeader = make("div", "flex flex-col space-y-1.5 p-6");
export const CardTitle = make("h2", "text-xl font-semibold tracking-tight");
export const CardDescription = make("p", "text-sm text-muted-foreground");
export const CardContent = make("div", "p-6 pt-0");
export const CardFooter = make("div", "flex items-center p-6 pt-0");
