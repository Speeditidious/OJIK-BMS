import UserDashboardPageClient from "./UserDashboardPageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ userId: "__static__" }];
}

export default function UserDashboardPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  return <UserDashboardPageClient params={params} />;
}
