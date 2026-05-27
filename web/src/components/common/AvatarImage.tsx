"use client";

import { useState } from "react";
import { getAvatarFallbackInitial } from "@/lib/avatar-core.mjs";

interface AvatarImageProps {
  src: string;
  alt: string;
  size: number;
  fallbackText: string;
  className?: string;
}

export function AvatarImage({ src, alt, size, fallbackText, className }: AvatarImageProps) {
  const [erroredSrc, setErroredSrc] = useState<string | null>(null);
  const hasError = erroredSrc === src;

  if (hasError) {
    return (
      <span
        aria-label={alt || undefined}
        role={alt ? "img" : undefined}
        style={{ width: size, height: size }}
        className={`inline-flex items-center justify-center bg-primary/20 text-primary font-medium ${className ?? ""}`}
      >
        {getAvatarFallbackInitial(fallbackText)}
      </span>
    );
  }

  return (
    // Small avatars are already bounded by `size`; skipping next/image avoids
    // Vercel image optimization work with minimal user-visible impact.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={className}
      onError={() => setErroredSrc(src)}
    />
  );
}
