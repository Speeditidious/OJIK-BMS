"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function UsernameRedirectPage() {
  const { username } = useParams<{ username: string }>();
  const router = useRouter();

  useEffect(() => {
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
