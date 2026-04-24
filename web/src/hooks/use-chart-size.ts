import { useCallback, useEffect, useState } from "react";
import type { RefCallback } from "react";

interface UseChartWidthOptions {
  active?: boolean;
  remeasureKey?: string | number | boolean | null;
  retryDelayMs?: number;
  maxRetryCount?: number;
}

/**
 * ResponsiveContainer 대체 훅.
 * 컨테이너 div의 width를 관찰하되, resize 이벤트를 debounce한다.
 *
 * @param debounceMs - resize 이벤트 debounce 시간 (기본 150ms)
 * @returns [containerRef, width] - ref를 div에 붙이고, width를 차트에 전달
 */
export function useChartWidth(
  debounceMs = 150,
  {
    active = true,
    remeasureKey = null,
    retryDelayMs = 120,
    maxRetryCount = 20,
  }: UseChartWidthOptions = {},
): [RefCallback<HTMLDivElement>, number] {
  const [element, setElement] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const containerRef = useCallback<RefCallback<HTMLDivElement>>((node) => {
    setElement(node);
  }, []);

  useEffect(() => {
    const el = element;
    if (!el) return;

    const measure = () => {
      const nextWidth = Math.round(el.getBoundingClientRect().width || el.clientWidth || 0);
      setWidth((prev) => (prev === nextWidth ? prev : nextWidth));
      return nextWidth;
    };

    const initialWidth = measure();

    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let retryTimeoutId: ReturnType<typeof setTimeout> | null = null;
    let frameId: number | null = null;
    let retryCount = 0;

    const clearRetry = () => {
      if (retryTimeoutId) {
        clearTimeout(retryTimeoutId);
        retryTimeoutId = null;
      }
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
        frameId = null;
      }
    };

    const scheduleRetry = () => {
      if (!active || retryCount >= maxRetryCount) return;
      clearRetry();
      retryTimeoutId = setTimeout(() => {
        retryCount += 1;
        frameId = window.requestAnimationFrame(() => {
          const measuredWidth = measure();
          if (measuredWidth === 0) {
            scheduleRetry();
          } else {
            clearRetry();
          }
        });
      }, retryDelayMs);
    };

    const measureAndRetry = () => {
      retryCount = 0;
      const measuredWidth = measure();
      if (measuredWidth === 0) {
        scheduleRetry();
      } else {
        clearRetry();
      }
    };

    if (initialWidth === 0 && active) {
      scheduleRetry();
    } else if (initialWidth > 0) {
      clearRetry();
    }

    const observer = new ResizeObserver((entries) => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        for (const entry of entries) {
          const newWidth = Math.round(entry.contentRect.width);
          setWidth((prev) => (prev === newWidth ? prev : newWidth));
          if (newWidth === 0) {
            retryCount = 0;
            scheduleRetry();
          } else {
            clearRetry();
          }
        }
      }, debounceMs);
    });

    const handleWindowResize = () => {
      measureAndRetry();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible") return;
      measureAndRetry();
    };

    observer.observe(el);
    window.addEventListener("resize", handleWindowResize);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      observer.disconnect();
      if (timeoutId) clearTimeout(timeoutId);
      clearRetry();
      window.removeEventListener("resize", handleWindowResize);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [active, debounceMs, element, maxRetryCount, remeasureKey, retryDelayMs]);

  return [containerRef, width];
}
