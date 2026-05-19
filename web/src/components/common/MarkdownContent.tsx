"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import rehypeSanitize from "rehype-sanitize";
import { cn } from "@/lib/utils";

interface MarkdownContentProps {
  children: string;
  className?: string;
}

/**
 * Renders markdown content with GFM support and HTML sanitization.
 * Styled to match the OJIK BMS design system (body text, muted links, etc.).
 */
export function MarkdownContent({ children, className }: MarkdownContentProps) {
  return (
    <div
      className={cn(
        // Base prose-like styling using design system tokens only
        "text-body leading-relaxed text-muted-foreground",
        "[&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-foreground [&_h1]:mb-3 [&_h1]:mt-5",
        "[&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mb-2 [&_h2]:mt-4",
        "[&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-foreground [&_h3]:mb-2 [&_h3]:mt-3",
        "[&_p]:mb-3 [&_p:last-child]:mb-0",
        "[&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul:last-child]:mb-0",
        "[&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol:last-child]:mb-0",
        "[&_li]:mb-1",
        "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:opacity-80",
        "[&_strong]:font-semibold [&_strong]:text-foreground",
        "[&_em]:italic",
        "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-label [&_code]:font-mono [&_code]:text-foreground",
        "[&_pre]:mb-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-muted [&_pre]:p-4",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_blockquote]:border-l-4 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-muted-foreground [&_blockquote]:my-3",
        "[&_hr]:border-border [&_hr]:my-4",
        "[&_table]:w-full [&_table]:text-label [&_table]:mb-3",
        "[&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-muted [&_th]:font-semibold [&_th]:text-foreground",
        "[&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} rehypePlugins={[rehypeSanitize]}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
