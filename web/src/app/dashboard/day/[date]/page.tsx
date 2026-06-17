import DashboardDayRedirectPageClient from "./DashboardDayRedirectPageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ date: "__static__" }];
}

export default function DashboardDayRedirectPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  return <DashboardDayRedirectPageClient params={params} />;
}
