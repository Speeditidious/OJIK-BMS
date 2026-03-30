import { useRef, useState, useEffect } from "react";
import type { RefObject } from "react";

/**
 * ResponsiveContainer 대체 훅.
 * 컨테이너 div의 width를 관찰하되, resize 이벤트를 debounce한다.
 *
 * @param debounceMs - resize 이벤트 debounce 시간 (기본 150ms)
 * @returns [containerRef, width] - ref를 div에 붙이고, width를 차트에 전달
 */
export function useChartWidth(debounceMs = 150): [RefObject<HTMLDivElement>, number] {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // 초기 width 설정
    setWidth(el.clientWidth);

    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const observer = new ResizeObserver((entries) => {
      // debounce: 마지막 resize 이벤트 후 debounceMs만큼 기다린 뒤 업데이트
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        for (const entry of entries) {
          const newWidth = Math.round(entry.contentRect.width);
          setWidth((prev) => (prev === newWidth ? prev : newWidth));
        }
      }, debounceMs);
    });

    observer.observe(el);

    return () => {
      observer.disconnect();
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [debounceMs]);

  return [containerRef, width];
}
