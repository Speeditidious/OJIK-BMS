"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getInitialBrowserPathname, restoreInitialBrowserUrlIfNeeded } from "@/lib/static-route";

export default function UsernameRedirectPage() {
  const { username: routeUsername } = useParams<{ username: string }>();
  const pathname = getInitialBrowserPathname();
  const pathnameUsername = pathname.match(/^\/u\/([^/?#]+)\/?$/)?.[1];
  const username = pathnameUsername ?? routeUsername;
  const router = useRouter();

  useEffect(() => {
    restoreInitialBrowserUrlIfNeeded();
    if (!username) return;
    api
      .get<{ id: string }>(`/users/${encodeURIComponent(username)}`)
      .then((user) => {
        router.replace(`/users/${user.id}/dashboard`);
      })
      .catch(() => {
        router.replace("/");
      });
  }, [username, router]);

  return null;
}
