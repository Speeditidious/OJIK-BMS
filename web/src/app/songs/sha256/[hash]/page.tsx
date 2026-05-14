"use client";

import { Suspense, use } from "react";
import SongDetailPage from "../../SongDetailPage";

interface Sha256SongPageProps {
  params: Promise<{ hash: string }>;
}

function Sha256SongPageContent({ params }: Sha256SongPageProps) {
  const { hash } = use(params);
  return <SongDetailPage params={Promise.resolve({ fumen_id: `sha256=${hash}` })} />;
}

export default function Sha256SongPage(props: Sha256SongPageProps) {
  return (
    <Suspense fallback={null}>
      <Sha256SongPageContent {...props} />
    </Suspense>
  );
}
