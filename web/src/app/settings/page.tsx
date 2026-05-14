"use client";

import { useEffect, useMemo, useRef, useState, Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Navbar } from "@/components/layout/navbar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Settings,
  Check,
  Loader2,
  Upload,
  Download,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth";
import { api, clearTokens, apiFetch } from "@/lib/api";
import { resolveAvatarUrl } from "@/lib/avatar";
import { useFavoriteTables } from "@/hooks/use-tables";
import {
  useScoreUpdatesPrefs,
  useUpdateScoreUpdatesPrefs,
  useClearTypeVisibility,
  useUpdateClearTypeVisibility,
  HIDEABLE_CLEAR_TYPES,
  LR2_MISSING_CLEAR_TYPES,
  type ClearTypeVisibilityPrefs,
  type ClearTypeVisibilityMode,
  type ClientVisibilityKey,
  type VisibilityMap,
} from "@/hooks/use-preferences";
import { Switch } from "@/components/ui/switch";
import { CLEAR_TYPE_LABELS } from "@/components/charts/ClearDistributionChart";

const EXPECTED_CONFIRMATION = "Yes, I want to delete my OJIK BMS account";

// ---------------------------------------------------------------------------
// Profile Tab
// ---------------------------------------------------------------------------

function ProfileTab() {
  const { t } = useTranslation();
  const { user } = useAuth(true);
  const { setUser } = useAuthStore();
  const queryClient = useQueryClient();

  const [username, setUsername] = useState("");
  const [bio, setBio] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  // Sync state from user on load
  useEffect(() => {
    if (!user) return;
    setUsername(user.username);
    setBio(user.bio ?? "");
  }, [user?.username, user?.bio]); // eslint-disable-line react-hooks/exhaustive-deps

  const displayUsername = username;

  const handleSave = async () => {
    if (!user) return;
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      const patch: Record<string, string | undefined> = {};
      if (displayUsername !== user.username) patch.username = displayUsername;
      const trimmedBio = bio.trim();
      const currentBio = user.bio ?? "";
      if (trimmedBio !== currentBio) patch.bio = trimmedBio;

      if (Object.keys(patch).length === 0) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
        return;
      }

      const updated = await api.patch<{
        id: string;
        username: string;
        bio: string | null;
        is_active: boolean;
        avatar_url: string | null;
      }>("/users/me", patch);
      setUser({ ...updated });
      queryClient.invalidateQueries({ queryKey: ["user-profile", updated.id] });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : t("settings.profile.saveFailed"));
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
      const updated = await api.postForm<{
        id: string;
        username: string;
        bio: string | null;
        is_active: boolean;
        avatar_url: string | null;
      }>("/users/me/avatar", form);
      setUser({ ...updated });
      queryClient.invalidateQueries({ queryKey: ["user-profile", updated.id] });
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : t("toasts.saveFailed"));
    } finally {
      setIsUploadingAvatar(false);
      e.target.value = "";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.profile.title")}</CardTitle>
        <CardDescription>{t("settings.profile.title")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
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
              Upload Image
            </Button>
            <p className="text-label text-muted-foreground">JPEG, PNG, WebP, GIF · max 5MB</p>
            {avatarError && <p className="text-label text-destructive">{avatarError}</p>}
          </div>
        </div>

        {/* Username */}
        <div>
          <label className="text-body font-medium mb-1 block">{t("settings.profile.username")}</label>
          <input
            type="text"
            value={displayUsername}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={user?.username ?? t("settings.profile.username")}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-body focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Bio */}
        <div>
          <label className="text-body font-medium mb-1 block">{t("settings.profile.about")}</label>
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={500}
            rows={3}
            placeholder={t("profile.about.empty")}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-body focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          <p className="text-label text-muted-foreground text-right">{bio.length}/500</p>
        </div>

        {saveError && <p className="text-body text-destructive">{saveError}</p>}

        <Button onClick={handleSave} disabled={isSaving} className="gap-2">
          {isSaving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saveSuccess ? (
            <Check className="h-4 w-4" />
          ) : null}
          {isSaving ? t("settings.profile.saving") : saveSuccess ? t("settings.profile.saved") : t("settings.profile.save")}
        </Button>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Preferences Tab
// ---------------------------------------------------------------------------

const SCORE_UPDATE_LABELS: { key: keyof ReturnType<typeof useScoreUpdatesPrefs>; label: string }[] = [
  { key: "score_updates_lamp_include_new_plays", label: "Lamp Upgrade — include new plays" },
  { key: "score_updates_score_include_new_plays", label: "Score Upgrade — include new plays" },
  { key: "score_updates_bp_include_new_plays", label: "BP Upgrade — include new plays" },
  { key: "score_updates_combo_include_new_plays", label: "Combo Upgrade — include new plays" },
];

const CLIENT_LABELS: Record<ClientVisibilityKey, string> = {
  all: "All",
  lr2: "LR2",
  beatoraja: "Beatoraja",
};

function ClearVisibilityCard() {
  const { t } = useTranslation();
  const { prefs } = useClearTypeVisibility();
  const { mutate: updatePrefs } = useUpdateClearTypeVisibility();
  const [selectedClient, setSelectedClient] = useState<ClientVisibilityKey>("all");

  const isGlobalActive = prefs.mode === "global";
  const isPerClientActive = prefs.mode === "per_client";

  const globalBucket = prefs.global;
  const perClientBucket = prefs[selectedClient];

  const hiddenOf = (bucket: VisibilityMap): Set<number> => {
    const s = new Set<number>();
    for (const [k, v] of Object.entries(bucket)) if (v === false) s.add(Number(k));
    return s;
  };

  const globalHidden = useMemo(() => hiddenOf(globalBucket), [globalBucket]);
  const perClientHidden = useMemo(() => hiddenOf(perClientBucket), [perClientBucket]);

  const perClientVisibleTypes = useMemo(() => {
    if (selectedClient === "lr2") {
      return HIDEABLE_CLEAR_TYPES.filter((ct) => !LR2_MISSING_CLEAR_TYPES.has(ct));
    }
    return HIDEABLE_CLEAR_TYPES;
  }, [selectedClient]);

  const handleSwitchMode = (nextMode: ClearTypeVisibilityMode) => {
    if (nextMode === prefs.mode) return;
    updatePrefs({ ...prefs, mode: nextMode });
  };

  const handleToggleGlobal = (ct: number) => {
    const current = globalBucket[String(ct)] ?? true;
    const nextBucket: VisibilityMap = { ...globalBucket };
    if (!current) delete nextBucket[String(ct)];
    else nextBucket[String(ct)] = false;
    updatePrefs({ ...prefs, global: nextBucket });
  };

  const handleTogglePerClient = (ct: number) => {
    const current = perClientBucket[String(ct)] ?? true;
    const nextBucket: VisibilityMap = { ...perClientBucket };
    if (!current) delete nextBucket[String(ct)];
    else nextBucket[String(ct)] = false;
    updatePrefs({ ...prefs, [selectedClient]: nextBucket } as ClearTypeVisibilityPrefs);
  };

  return (
    <Card id="clear-visibility">
      <CardHeader>
        <CardTitle className="text-base">{t("settings.display.title")}</CardTitle>
        <CardDescription>
          {t("settings.display.clearDistribution")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Global section */}
        <div className="rounded-md border border-border p-4 space-y-3">
          <div className="flex items-center gap-3">
            <Switch
              checked={isGlobalActive}
              onCheckedChange={(v) => handleSwitchMode(v ? "global" : "per_client")}
              aria-label="Enable global mode"
            />
            <div className="flex-1">
              <p className="text-body font-medium">Global</p>
              <p className="text-label text-muted-foreground">
                Applied uniformly across all views.
              </p>
            </div>
          </div>

          <div
            className={
              "space-y-2 pl-1 " +
              (isGlobalActive ? "" : "opacity-50 pointer-events-none select-none")
            }
            aria-hidden={!isGlobalActive}
          >
            {HIDEABLE_CLEAR_TYPES.map((ct) => (
              <label key={ct} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!globalHidden.has(ct)}
                  onChange={() => handleToggleGlobal(ct)}
                  disabled={!isGlobalActive}
                  className="h-4 w-4 rounded border-input accent-primary cursor-pointer disabled:cursor-not-allowed"
                />
                <span className="text-body">{CLEAR_TYPE_LABELS[ct] ?? String(ct)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Per-client (includes All) section */}
        <div className="rounded-md border border-border p-4 space-y-3">
          <div className="flex items-center gap-3">
            <Switch
              checked={isPerClientActive}
              onCheckedChange={(v) => handleSwitchMode(v ? "per_client" : "global")}
              aria-label="Enable per-client mode"
            />
            <div className="flex-1">
              <p className="text-body font-medium">{t("settings.display.sourceClient")}</p>
              <p className="text-label text-muted-foreground">
                Configured independently per client view.
              </p>
            </div>
          </div>

          <div
            className={
              "space-y-3 pl-1 " +
              (isPerClientActive ? "" : "opacity-50 pointer-events-none select-none")
            }
            aria-hidden={!isPerClientActive}
          >
            <div className="flex items-center gap-2">
              <label className="text-body font-medium">Client</label>
              <select
                value={selectedClient}
                onChange={(e) => setSelectedClient(e.target.value as ClientVisibilityKey)}
                disabled={!isPerClientActive}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-body focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed"
              >
                <option value="all">{CLIENT_LABELS.all}</option>
                <option value="lr2">{CLIENT_LABELS.lr2}</option>
                <option value="beatoraja">{CLIENT_LABELS.beatoraja}</option>
              </select>
            </div>

            <div className="space-y-2">
              {perClientVisibleTypes.map((ct) => (
                <label key={ct} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!perClientHidden.has(ct)}
                    onChange={() => handleTogglePerClient(ct)}
                    disabled={!isPerClientActive}
                    className="h-4 w-4 rounded border-input accent-primary cursor-pointer disabled:cursor-not-allowed"
                  />
                  <span className="text-body">{CLEAR_TYPE_LABELS[ct] ?? String(ct)}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PreferencesTab() {
  const { t } = useTranslation();
  const { data: favTables } = useFavoriteTables();
  const scorePrefs = useScoreUpdatesPrefs();
  const { mutate: updateScorePrefs } = useUpdateScoreUpdatesPrefs();

  return (
    <div className="space-y-4">
      {/* Favorite tables */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("tables.sidebar.favorites")}</CardTitle>
          <CardDescription>
            {t("dashboard.tableClear.settingsDescription")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {favTables && favTables.length > 0 ? (
            <ol className="space-y-1 text-body">
              {favTables.map((tbl, i) => (
                <li key={tbl.id} className="flex items-center gap-2">
                  <span className="text-muted-foreground text-label w-5 text-right">{i + 1}.</span>
                  <span>
                    {tbl.symbol && <span className="mr-1 text-muted-foreground">{tbl.symbol}</span>}
                    {tbl.name}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-body text-muted-foreground">{t("dashboard.tableClear.noTableData")}</p>
          )}
          <div className="pt-1">
            <Link href="/tables">
              <Button variant="outline" size="sm" className="gap-2">
                <ExternalLink className="h-4 w-4" />
                {t("tables.hub.title")}
              </Button>
            </Link>
            <p className="text-label text-muted-foreground mt-2">
              {t("dashboard.tableClear.settingsAria")}
            </p>
          </div>
        </CardContent>
      </Card>

      <Separator />

      {/* Score updates new-play toggle */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Score Updates Display</CardTitle>
          <CardDescription>
            Configure whether to include new plays (first play) in each category of the score updates view.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {SCORE_UPDATE_LABELS.map(({ key, label }) => (
            <label key={key} className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={scorePrefs[key]}
                onChange={(e) => updateScorePrefs({ [key]: e.target.checked })}
                className="h-4 w-4 rounded border-input accent-primary cursor-pointer"
              />
              <span className="text-body">{label}</span>
            </label>
          ))}
        </CardContent>
      </Card>

      <Separator />

      <ClearVisibilityCard />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Account Management Tab
// ---------------------------------------------------------------------------

type DeleteStep = "idle" | "confirming" | "verified" | "deleting";

function AccountTab() {
  const { t } = useTranslation();
  const [syncStatus, setSyncStatus] = useState<{ last_synced_at: string | null } | null>(null);
  const [oauthAccounts, setOauthAccounts] = useState<
    { provider: string; provider_username: string | null }[]
  >([]);

  const router = useRouter();
  const searchParams = useSearchParams();

  // Read delete_token from URL on first render (popup-blocked fallback redirect)
  // useRef freezes the initial searchParams so we don't re-derive on re-renders
  const initSearchParams = useRef(searchParams);
  const urlToken = initSearchParams.current.get("delete_token");

  const [deleteOpen, setDeleteOpen] = useState(!!urlToken);
  const [deleteStep, setDeleteStep] = useState<DeleteStep>(urlToken ? "verified" : "idle");
  const [deleteToken, setDeleteToken] = useState<string | null>(urlToken);
  const [confirmText, setConfirmText] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Load sync status and oauth accounts
  useEffect(() => {
    api.get<{ last_synced_at: string | null }>("/sync/status")
      .then((data) => setSyncStatus(data))
      .catch(() => {});
    api.get<{ provider: string; provider_username: string | null }[]>("/users/me/oauth")
      .then((data) => setOauthAccounts(data))
      .catch(() => {});
  }, []);

  // Clean URL if we arrived via the popup-blocked fallback redirect
  useEffect(() => {
    if (urlToken) {
      router.replace(`/settings?tab=account`, { scroll: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Listen for popup postMessage
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === "ojik_delete_verified") {
        setDeleteToken(event.data.token as string);
        setDeleteStep("verified");
        setVerifyError(null);
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const handleOpenDeleteModal = () => {
    setDeleteStep("confirming");
    setDeleteToken(null);
    setConfirmText("");
    setDeleteError(null);
    setVerifyError(null);
    setDeleteOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setDeleteOpen(false);
    setDeleteStep("idle");
    setDeleteToken(null);
    setConfirmText("");
    setDeleteError(null);
    setVerifyError(null);
  };

  const openDeleteVerification = () => {
    const width = 500;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    const popup = window.open(
      `${apiUrl}/auth/discord/login?state=delete_verify`,
      "ojik_delete_verify",
      `width=${width},height=${height},left=${left},top=${top},popup=yes`,
    );

    if (!popup || popup.closed) {
      setVerifyError(null);
      // Fallback: redirect current tab
      window.location.href = `${apiUrl}/auth/discord/login?state=delete_verify_redirect`;
    }
  };

  const handleDeleteAccount = async () => {
    if (!deleteToken) return;
    setDeleteStep("deleting");
    setDeleteError(null);

    try {
      await apiFetch("/users/me", {
        method: "DELETE",
        body: JSON.stringify({
          verification_token: deleteToken,
          confirmation_text: confirmText,
        }),
      });
      clearTokens();
      window.location.href = "/";
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t("toasts.saveFailed"));
      setDeleteStep("verified");
    }
  };

  const isConfirmValid = confirmText === EXPECTED_CONFIRMATION;

  return (
    <div className="space-y-4">
      {/* Connected accounts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connected Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {oauthAccounts.length > 0 ? (
            oauthAccounts.map((acc) => (
              <div key={acc.provider} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  {acc.provider === "discord" && (
                    <svg className="h-5 w-5 text-muted-foreground" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026c.462-.62.874-1.275 1.226-1.963.021-.04.001-.088-.041-.104a13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z" />
                    </svg>
                  )}
                  <span className="text-body font-medium capitalize">{acc.provider}</span>
                  {acc.provider_username && (
                    <span className="text-label text-muted-foreground">{acc.provider_username}</span>
                  )}
                </div>
                <span className="text-label text-primary">Connected</span>
              </div>
            ))
          ) : (
            <p className="text-body text-muted-foreground">No connected accounts.</p>
          )}
        </CardContent>
      </Card>

      {/* Sync status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sync Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-body">
            <span className="text-muted-foreground">Last synced: </span>
            {syncStatus?.last_synced_at ? (
              <span className="font-medium">
                {new Date(syncStatus.last_synced_at).toLocaleString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            ) : (
              <span className="text-muted-foreground">{t("profile.info.neverSynced")}</span>
            )}
          </div>
          <Link href="/download">
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="h-4 w-4" />
              {t("common.nav.download")}
            </Button>
          </Link>
        </CardContent>
      </Card>

      <Separator />

      {/* Danger zone */}
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Danger Zone
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="text-body font-medium mb-1">{t("settings.account.deleteAccount")}</p>
            <ul className="text-label text-muted-foreground space-y-0.5 mb-3 list-disc list-inside">
              <li>All play records will be permanently deleted</li>
              <li>Favorites, tags, and settings will all be deleted</li>
              <li>Deleted data cannot be recovered</li>
            </ul>
            <Button variant="destructive" size="sm" onClick={handleOpenDeleteModal}>
              {t("settings.account.deleteAccount")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteOpen} onOpenChange={(open) => { if (!open) handleCloseDeleteModal(); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t("settings.account.deleteAccount")}
            </DialogTitle>
            <DialogDescription>
              This action cannot be undone. Your account and all data will be permanently deleted.
            </DialogDescription>
          </DialogHeader>

          {deleteStep === "confirming" && (
            <div className="space-y-4">
              <p className="text-body">
                To continue, please verify your identity with your Discord account.
              </p>
              {verifyError && <p className="text-label text-destructive">{verifyError}</p>}
              <Button onClick={openDeleteVerification} variant="outline" className="w-full gap-2">
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026c.462-.62.874-1.275 1.226-1.963.021-.04.001-.088-.041-.104a13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z" />
                </svg>
                Verify with Discord
              </Button>
            </div>
          )}

          {(deleteStep === "verified" || deleteStep === "deleting") && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-body text-green-500">
                <Check className="h-4 w-4" />
                Discord verification complete
              </div>
              <div>
                <p className="text-body mb-2">To delete your account, type the following phrase exactly:</p>
                <p className="text-label font-mono bg-muted px-3 py-2 rounded-md mb-2 break-all">
                  {EXPECTED_CONFIRMATION}
                </p>
                <input
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="Type the phrase above"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-body focus:outline-none focus:ring-2 focus:ring-ring"
                  disabled={deleteStep === "deleting"}
                />
              </div>
              {deleteError && <p className="text-label text-destructive">{deleteError}</p>}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDeleteModal} disabled={deleteStep === "deleting"}>
              {t("common.actions.cancel")}
            </Button>
            {(deleteStep === "verified" || deleteStep === "deleting") && (
              <Button
                variant="destructive"
                onClick={handleDeleteAccount}
                disabled={!isConfirmValid || deleteStep === "deleting"}
                className="gap-2"
              >
                {deleteStep === "deleting" && <Loader2 className="h-4 w-4 animate-spin" />}
                {t("settings.account.confirmDelete")}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Settings Page
// ---------------------------------------------------------------------------

function SettingsContent() {
  const { t } = useTranslation();
  const { isLoading } = useAuth(true);
  const searchParams = useSearchParams();
  const router = useRouter();

  const tab = searchParams.get("tab") ?? "profile";

  const handleTabChange = (value: string) => {
    router.replace(`/settings?tab=${value}`, { scroll: false });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        <Navbar />
        <main className="container mx-auto px-4 py-8 max-w-2xl">
          <div className="flex items-center gap-3 mb-8">
            <Settings className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">{t("common.actions.settings")}</h1>
          </div>

          <Tabs value={tab} onValueChange={handleTabChange}>
            <TabsList className="mb-6">
              <TabsTrigger value="profile">{t("settings.tabs.profile")}</TabsTrigger>
              <TabsTrigger value="preferences">{t("settings.tabs.privacy")}</TabsTrigger>
              <TabsTrigger value="account">{t("settings.tabs.account")}</TabsTrigger>
            </TabsList>

            <TabsContent value="profile">
              <ProfileTab />
            </TabsContent>

            <TabsContent value="preferences">
              <PreferencesTab />
            </TabsContent>

            <TabsContent value="account">
              <AccountTab />
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </TooltipProvider>
  );
}

export default function SettingsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
        </div>
      }
    >
      <SettingsContent />
    </Suspense>
  );
}
