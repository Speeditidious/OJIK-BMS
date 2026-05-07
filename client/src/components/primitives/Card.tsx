import type { HTMLAttributes, ReactNode } from "react";

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section className={`card${className ? ` ${className}` : ""}`} {...rest}>
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  actions,
  className,
}: {
  title: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={`card-hd${className ? ` ${className}` : ""}`}>
      <div className="card-title">{title}</div>
      {actions ? <div className="card-actions">{actions}</div> : null}
    </header>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={`card-bd${className ? ` ${className}` : ""}`}>{children}</div>;
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={`card-ft${className ? ` ${className}` : ""}`}>{children}</div>;
}
