"use client";

interface AvatarImageProps {
  src: string;
  alt: string;
  size: number;
  className?: string;
}

export function AvatarImage({ src, alt, size, className }: AvatarImageProps) {
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
    />
  );
}
