export function decodeHtmlEntities(value: string): string {
  return value
    .replace(/&#(\d+);/gu, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/giu, (_, code) => String.fromCodePoint(parseInt(code, 16)))
    .replace(/&amp;/gu, "&")
    .replace(/&lt;/gu, "<")
    .replace(/&gt;/gu, ">")
    .replace(/&quot;/gu, "\"")
    .replace(/&#39;/gu, "'")
    .replace(/&nbsp;/gu, " ");
}

export function stripHtmlToLines(fragment: string): string[] {
  const normalized = fragment
    .replace(/<(script|style|svg|button|noscript)\b[\s\S]*?<\/\1>/giu, " ")
    .replace(/<br\s*\/?>/giu, "\n")
    .replace(/<\/(p|div|section|article|h1|h2|h3|h4|li|ul|ol)>/giu, "\n")
    .replace(/<(p|div|section|article|h1|h2|h3|h4|li|ul|ol)\b[^>]*>/giu, "\n")
    .replace(/<[^>]+>/gu, " ");

  return decodeHtmlEntities(normalized)
    .split(/\n+/u)
    .map((line) => line.replace(/\s+/gu, " ").trim())
    .filter(Boolean);
}

export function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/gu, " ").trim();
}

export function truncateForPrompt(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength)}...`;
}
