import UserProfilePageClient from "./UserProfilePageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ userId: "__static__" }];
}

export default function UserProfilePage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  return <UserProfilePageClient params={params} />;
}
