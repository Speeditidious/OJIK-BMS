"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // next-themes는 클라이언트에서만 동작하므로,
  // 서버 렌더링 중에는 아이콘을 표시하지 않아야 hydration mismatch를 방지한다.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    // SSR/hydration 중: 레이아웃 shift 방지를 위해 빈 placeholder 렌더링
    return <div className="rounded-md p-2 h-9 w-9" aria-hidden="true" />;
  }

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "rounded-md p-2 transition-colors cursor-pointer",
        className ?? "text-muted-foreground hover:text-foreground hover:bg-secondary"
      )}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}
