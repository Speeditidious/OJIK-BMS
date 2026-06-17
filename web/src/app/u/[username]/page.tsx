import UsernameRedirectPageClient from "./UsernameRedirectPageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ username: "__static__" }];
}

export default function UsernameRedirectPage() {
  return <UsernameRedirectPageClient />;
}
