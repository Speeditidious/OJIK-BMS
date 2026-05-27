function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeMarkdownLabel(value) {
  return value.replace(/([\\\[\]])/g, "\\$1");
}

/**
 * Preprocess markdown to turn @username and #123 tokens into markdown links,
 * skipping content inside code spans and fenced code blocks.
 */
export function preprocessMarkdownMentions(text, mentions = []) {
  const parts = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  const placeholders = [];

  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part;

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
    .replace(/\u0000OJIK_MENTION_(\d+)\u0000/g, (_, index) => placeholders[Number(index)] ?? "");
}
