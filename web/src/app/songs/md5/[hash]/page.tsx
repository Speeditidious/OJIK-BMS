import Md5SongPageClient from "./Md5SongPageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ hash: "__static__" }];
}

export default function Md5SongPage({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  return <Md5SongPageClient params={params} />;
}
