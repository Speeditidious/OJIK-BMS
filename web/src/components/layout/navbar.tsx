"use client";

import { useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Music2,
  Table2,
  ListMusic,
  Download,
  LayoutDashboard,
  Settings,
  LogOut,
  UserCircle,
  Trophy,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

import { cn } from "@/lib/utils";
import { resolveAvatarUrl } from "@/lib/avatar";
import { useAuthStore } from "@/stores/auth";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

const navItems = [
  { href: "/ranking", label: "랭킹", icon: Trophy },
  { href: "/tables", label: "난이도표", icon: Table2 },
  { href: "/songs", label: "차분 목록", icon: Music2 },
  { href: "/custom", label: "커스텀", icon: ListMusic },
  { href: "/download", label: "클라이언트 다운로드", icon: Download },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isInitialized, fetchUser, logout } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      fetchUser();
    }
  }, [isInitialized, fetchUser]);

  return (
    <nav className="sticky top-0 z-50 border-b border-white/20 bg-primary/90 backdrop-blur supports-[backdrop-filter]:bg-primary/80 dark:border-border dark:bg-card/95 dark:supports-[backdrop-filter]:dark:bg-card/60">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-xl mr-8 text-primary-foreground dark:text-foreground">
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
                  "flex items-center gap-2 px-3 py-2 rounded-md text-body font-medium transition-colors",
                  isActive
                    ? "bg-white/20 text-white dark:bg-primary/10 dark:text-primary"
                    : "text-white hover:bg-white/10 dark:text-foreground dark:hover:bg-secondary"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-1">
          {/* Dark/Light mode toggle */}
          <ThemeToggle className="text-white hover:bg-white/10 dark:text-foreground dark:hover:bg-secondary" />

          <div className="w-5" />

          {isInitialized && (
            user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="rounded-full focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer">
                    {user.avatar_url ? (
                      <Image
                        src={resolveAvatarUrl(user.avatar_url)}
                        alt={user.username}
                        width={32}
                        height={32}
                        className="rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-white/25 flex items-center justify-center text-label font-medium text-white dark:bg-primary/20 dark:text-primary">
                        {user.username.charAt(0).toUpperCase()}
                      </div>
                    )}
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <div className="px-2 py-1.5 flex items-center gap-2 border-b mb-1 pointer-events-none">
                    {user.avatar_url ? (
                      <Image
                        src={resolveAvatarUrl(user.avatar_url)}
                        alt={user.username}
                        width={24}
                        height={24}
                        className="rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-6 h-6 rounded-full bg-white/25 flex items-center justify-center text-[10px] font-medium text-white dark:bg-primary/20 dark:text-primary">
                        {user.username.charAt(0).toUpperCase()}
                      </div>
                    )}
                    <span className="text-label font-medium truncate">{user.username}</span>
                  </div>
                  <DropdownMenuItem onClick={() => router.push(`/users/${user.id}/dashboard`)}>
                    <LayoutDashboard className="h-4 w-4" />
                    대시보드
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => router.push(`/users/${user.id}`)}>
                    <UserCircle className="h-4 w-4" />
                    프로필
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => router.push("/settings")}>
                    <Settings className="h-4 w-4" />
                    설정
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={logout}
                    className="text-destructive focus:text-destructive"
                  >
                    <LogOut className="h-4 w-4" />
                    로그아웃
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <button
                onClick={() => router.push("/login")}
                className="rounded-full p-1 text-white hover:bg-white/10 dark:text-foreground dark:hover:bg-secondary transition-colors cursor-pointer"
                aria-label="로그인"
              >
                <UserCircle className="h-7 w-7" />
              </button>
            )
          )}
        </div>
      </div>
    </nav>
  );
}
