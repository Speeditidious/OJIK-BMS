import Sha256SongPageClient from "./Sha256SongPageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ hash: "__static__" }];
}

export default function Sha256SongPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  return <Sha256SongPageClient params={params} />;
}
