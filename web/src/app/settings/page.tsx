"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, Check, Loader2, Upload, Download } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/lib/api";
import { resolveAvatarUrl } from "@/lib/avatar";

export default function SettingsPage() {
  const { user, isLoading } = useAuth(true);
  const { setUser } = useAuthStore();

  const [username, setUsername] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const [syncStatus, setSyncStatus] = useState<{ last_synced_at: string | null } | null>(null);

  // Sync local username state once user is loaded
  const displayUsername = username || user?.username || "";

  useEffect(() => {
    if (!user) return;
    api.get<{ last_synced_at: string | null }>("/sync/status")
      .then((data) => setSyncStatus(data))
      .catch(() => {});
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      const updated = await api.patch<{
        id: string;
        username: string;
        is_active: boolean;
        is_public: boolean;
        avatar_url: string | null;
      }>("/users/me", {
        username: displayUsername !== user.username ? displayUsername : undefined,
        is_public: user.is_public,
      });
      setUser({ ...updated });
      setUsername("");
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "저장에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingAvatar(true);
    setAvatarError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const updated = await api.postForm<{ id: string; username: string; is_active: boolean; is_public: boolean; avatar_url: string | null }>("/users/me/avatar", form);
      setUser({ ...updated });
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : "업로드에 실패했습니다.");
    } finally {
      setIsUploadingAvatar(false);
      e.target.value = "";
    }
  };

  const handleTogglePublic = async () => {
    if (!user) return;
    try {
      const updated = await api.patch<{
        id: string;
        username: string;
        is_active: boolean;
        is_public: boolean;
        avatar_url: string | null;
      }>("/users/me", { is_public: !user.is_public });
      setUser({ ...updated });
    } catch {
      // ignore
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <div className="flex items-center gap-3 mb-8">
          <Settings className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">설정</h1>
        </div>

        <div className="space-y-6">
          {/* Profile settings */}
          <Card>
            <CardHeader>
              <CardTitle>프로필</CardTitle>
              <CardDescription>유저네임, 프로필 이미지 및 공개 설정</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Avatar */}
              <div className="flex items-center gap-4">
                {user?.avatar_url ? (
                  <Image
                    src={resolveAvatarUrl(user.avatar_url)}
                    alt={user.username}
                    width={64}
                    height={64}
                    className="rounded-full object-cover"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-xl font-medium text-primary">
                    {user?.username.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="space-y-1">
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={handleAvatarChange}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => avatarInputRef.current?.click()}
                    disabled={isUploadingAvatar}
                  >
                    {isUploadingAvatar ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    이미지 업로드
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    JPEG, PNG, WebP, GIF · 최대 5MB
                  </p>
                  {avatarError && (
                    <p className="text-xs text-destructive">{avatarError}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">유저네임</label>
                <input
                  type="text"
                  value={displayUsername}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={user?.username ?? "유저네임"}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">프로필 공개</p>
                  <p className="text-xs text-muted-foreground">
                    다른 사용자가 내 프로필을 볼 수 있습니다
                  </p>
                </div>
                <Button
                  variant={user?.is_public ? "default" : "outline"}
                  size="sm"
                  onClick={handleTogglePublic}
                >
                  {user?.is_public ? "공개" : "비공개"}
                </Button>
              </div>

              {saveError && (
                <p className="text-sm text-destructive">{saveError}</p>
              )}

              <Button onClick={handleSave} disabled={isSaving} className="gap-2">
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : saveSuccess ? (
                  <Check className="h-4 w-4" />
                ) : null}
                {saveSuccess ? "저장됨" : "저장"}
              </Button>
            </CardContent>
          </Card>

          {/* Connected accounts */}
          <Card>
            <CardHeader>
              <CardTitle>연결된 계정</CardTitle>
              <CardDescription>소셜 로그인 계정 연결 현황</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  <svg
                    className="h-5 w-5 text-muted-foreground"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026c.462-.62.874-1.275 1.226-1.963.021-.04.001-.088-.041-.104a13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z" />
                  </svg>
                  <span className="text-sm font-medium">Discord</span>
                </div>
                <span className="text-xs text-primary">연결됨</span>
              </div>
            </CardContent>
          </Card>

          {/* Sync settings */}
          <Card>
            <CardHeader>
              <CardTitle>동기화</CardTitle>
              <CardDescription>OJIK BMS 클라이언트 연결 상태</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-sm">
                <span className="text-muted-foreground">마지막 동기화: </span>
                {syncStatus?.last_synced_at ? (
                  <span className="font-medium">
                    {new Date(syncStatus.last_synced_at).toLocaleString("ko-KR", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                ) : (
                  <span className="text-muted-foreground">없음</span>
                )}
              </div>
              <div className="pt-2">
                <Link href="/download">
                  <Button variant="outline" className="gap-2">
                    <Download className="h-4 w-4" />
                    클라이언트 다운로드
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>

          {/* Danger zone */}
          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">위험 구역</CardTitle>
              <CardDescription>되돌릴 수 없는 작업입니다</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="destructive" size="sm" disabled>
                계정 삭제 (준비 중)
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
