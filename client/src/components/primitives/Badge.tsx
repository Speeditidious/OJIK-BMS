import type { ReactNode } from "react";

type Tone = "success" | "warn" | "danger" | "muted" | "primary" | "accent";

export function Badge({
  tone = "muted",
  icon,
  children,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      {icon}
      {children}
    </span>
  );
}
