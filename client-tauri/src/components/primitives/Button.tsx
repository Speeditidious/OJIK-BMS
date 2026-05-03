import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "default" | "primary" | "accent" | "danger" | "ghost";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  block?: boolean;
  iconOnly?: boolean;
  leadingIcon?: ReactNode;
}

export function Button({
  variant = "default",
  size = "md",
  block,
  iconOnly,
  leadingIcon,
  className,
  children,
  type,
  ...rest
}: ButtonProps) {
  const classes = [
    "btn",
    variant !== "default" ? `btn-${variant}` : "",
    size === "sm" ? "btn-sm" : size === "lg" ? "btn-lg" : "",
    block ? "btn-block" : "",
    iconOnly ? "btn-icon" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type={type ?? "button"} className={classes} {...rest}>
      {leadingIcon}
      {children}
    </button>
  );
}
