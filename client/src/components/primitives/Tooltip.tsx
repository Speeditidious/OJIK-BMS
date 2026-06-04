import type { ReactNode } from "react";

export interface TooltipProps {
  /** The element that triggers the tooltip on hover/focus. */
  children: ReactNode;
  /** Tooltip body text shown on hover/focus. */
  text: string;
  /** Which side of the trigger the bubble appears on. */
  side?: "top" | "bottom";
}

/**
 * Wraps any element and reveals a styled tooltip bubble when the wrapper is hovered or focused.
 */
export function Tooltip({ children, text, side = "top" }: TooltipProps) {
  return (
    <div className={`tooltip-wrap tooltip-${side}`}>
      {children}
      <span className="tooltip-bubble" role="tooltip">
        {text}
      </span>
    </div>
  );
}
