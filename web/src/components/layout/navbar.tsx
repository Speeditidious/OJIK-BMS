"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Music2,
  Table2,
  ListMusic,
  LayoutDashboard,
  MessageCircle,
  Download,
  Settings,
  LogOut,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { resolveAvatarUrl } from "@/lib/avatar";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";

const navItems = [
  { href: "/dashboard", label: "대시보드", icon: LayoutDashboard },
  { href: "/tables", label: "난이도표", icon: Table2 },
  { href: "/songs", label: "곡 목록", icon: Music2 },
  { href: "/custom", label: "커스텀", icon: ListMusic },
  { href: "/chat", label: "챗봇", icon: MessageCircle },
  { href: "/download", label: "클라이언트 다운로드", icon: Download },
];

export function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  return (
    <nav className="border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-xl mr-8">
          <Image src="/ojikbms_logo.png" alt="OJIK BMS" width={24} height={24} />
          <span>OJIK BMS</span>
        </Link>

        {/* Navigation links */}
        <div className="flex items-center gap-1 flex-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          {user && (
            <div className="flex items-center gap-2">
              {user.avatar_url ? (
                <Image
                  src={resolveAvatarUrl(user.avatar_url)}
                  alt={user.username}
                  width={28}
                  height={28}
                  className="rounded-full object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium text-primary">
                  {user.username.charAt(0).toUpperCase()}
                </div>
              )}
              <span className="text-sm text-muted-foreground hidden sm:block">{user.username}</span>
            </div>
          )}
          <Link href="/settings">
            <Button variant="ghost" size="icon" aria-label="설정">
              <Settings className="h-4 w-4" />
            </Button>
          </Link>
          <Button variant="ghost" size="icon" onClick={logout} aria-label="로그아웃">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </nav>
  );
}
