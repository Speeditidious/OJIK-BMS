"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import rehypeSanitize from "rehype-sanitize";
import { cn } from "@/lib/utils";

interface MarkdownMention {
  source_text: string;
  user: {
    id: string;
    username: string;
  };
}

interface MarkdownContentProps {
  children: string;
  className?: string;
  mentions?: MarkdownMention[];
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeMarkdownLabel(value: string): string {
  return value.replace(/([\\\[\]])/g, "\\$1");
}

/**
 * Preprocess markdown to turn @username and #123 tokens into markdown links,
 * skipping content inside code spans and fenced code blocks.
 */
function preprocessMentions(text: string, mentions: MarkdownMention[] = []): string {
  // Split on fenced code blocks and inline code spans to leave them untouched
  const parts = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  const placeholders: string[] = [];

  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // inside a code block

      const withResolvedMentions = mentions.reduce((current, mention) => {
        if (!mention.source_text || !mention.user.id || !mention.user.username) return current;
        const pattern = new RegExp(`(?<![.\\w@])${escapeRegExp(mention.source_text)}(?![A-Za-z0-9_.-])`, "gi");
        return current.replace(pattern, () => {
          const placeholder = `\u0000OJIK_MENTION_${placeholders.length}\u0000`;
          placeholders.push(`[@${escapeMarkdownLabel(mention.user.username)}](/users/${mention.user.id}/dashboard)`);
          return placeholder;
        });
      }, part);

      return withResolvedMentions
        .replace(/(?<![.\w@])@([A-Za-z0-9_]+(?:[._-][A-Za-z0-9_]+)*)/g, "[@$1](/u/$1)")
        .replace(/(?<![.\w#])#([1-9][0-9]{0,9})(?!\w)/g, "[#$1](/issues/$1)");
    })
    .join("")
    .replace(/\u0000OJIK_MENTION_(\d+)\u0000/g, (_, index: string) => placeholders[Number(index)] ?? "");
}

/**
 * Renders markdown content with GFM support and HTML sanitization.
 * Resolved @mentions link to user dashboards; unresolved @mentions use username redirects.
 */
export function MarkdownContent({ children, className, mentions }: MarkdownContentProps) {
  return (
    <div
      className={cn(
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
        {preprocessMentions(children, mentions)}
      </ReactMarkdown>
    </div>
  );
}
