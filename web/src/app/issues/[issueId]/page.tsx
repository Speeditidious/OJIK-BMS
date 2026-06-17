import IssuePageClient from "./IssuePageClient";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ issueId: "__static__" }];
}

export default function IssuePage() {
  return <IssuePageClient />;
}
