import type { ArticleContent, FetchLike, SourceAdapter, SourceListItem } from "../types.ts";
import { fetchText } from "../utils/http.ts";
import { decodeHtmlEntities, normalizeWhitespace, stripHtmlToLines } from "../utils/text.ts";

const NEWS_URL = "https://www.anthropic.com/news";

export class AnthropicNewsAdapter implements SourceAdapter {
  readonly id = "anthropic-news";
  readonly name = "Anthropic";
  readonly rssUrl = NEWS_URL;

  constructor(private readonly fetchImpl: FetchLike = fetch) {}

  async listLatest(): Promise<SourceListItem[]> {
    const html = await fetchText(this.rssUrl, undefined, this.fetchImpl);
    return parseAnthropicListItems(html, this.rssUrl);
  }

  async fetchArticle(item: SourceListItem): Promise<ArticleContent> {
    const html = await fetchText(item.url, undefined, this.fetchImpl);
    const bodyText = extractArticleBody(html, item);

    return {
      sourceId: this.id,
      sourceName: this.name,
      title: item.title,
      url: item.url,
      publishedAt: item.publishedAt,
      category: item.category,
      bodyText,
    };
  }
}

export function parseAnthropicListItems(html: string, baseUrl = NEWS_URL): SourceListItem[] {
  const matches = [...html.matchAll(/<a\b[^>]*>[\s\S]*?<\/a>/giu)];
  return matches
    .filter((match) => {
      const anchor = match[0];
      const href = extractHref(anchor);
      if (!href) {
        return false;
      }

      if (!href.startsWith("/news/") && !href.startsWith(`${new URL(baseUrl).origin}/news/`)) {
        return false;
      }

      if (!hasClassToken(extractClassAttribute(anchor), "listItem")) {
        return false;
      }

      if (!/<time\b[^>]*>/iu.test(anchor)) {
        return false;
      }

      return true;
    })
    .map((match) => {
      const anchor = match[0];
      const href = extractHref(anchor);
      if (!href) {
        throw new Error("Missing href for news list item.");
      }

      const title = extractByClass(anchor, "title");
      if (!title) {
        throw new Error(`Missing item title for ${href}`);
      }

      const rawDate = extractTagValue(anchor, "time");
      if (!rawDate) {
        throw new Error(`Missing item date for ${href}`);
      }

      const parsedDate = new Date(rawDate);
      if (!Number.isFinite(parsedDate.getTime())) {
        throw new Error(`Invalid item date for ${href}: ${rawDate}`);
      }

      const category = extractByClass(anchor, "subject") ?? "Uncategorized";
      const normalizedUrl = normalizeArticleUrl(href, baseUrl);

      return {
        id: normalizedUrl,
        title,
        url: normalizedUrl,
        publishedAt: parsedDate.toISOString(),
        category,
      };
    });
}

export function extractArticleBody(
  html: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): string {
  const bodyMatch = html.match(
    /<div[^>]*class=(["'])[^"']*__body[^"']*\1[^>]*>([\s\S]*?)<\/div>\s*<\/article>/iu,
  );
  if (!bodyMatch) {
    throw new Error("Article body container not found.");
  }
  return normalizeArticleBody(bodyMatch[2], item);
}

function hasClassToken(classValue: string, token: string): boolean {
  return classValue
    .split(/\s+/u)
    .filter(Boolean)
    .some((className) => className.includes(token));
}

function isNoiseLine(
  line: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): boolean {
  const normalized = normalizeWhitespace(line);
  const normalizedLower = normalized.toLocaleLowerCase("en-US");
  const publishedDate = new Date(item.publishedAt).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  return [
    "Share",
    "Share on Twitter",
    "Share on LinkedIn",
    item.title,
    item.category,
    publishedDate,
  ].some((noise) => normalizeWhitespace(String(noise)).toLocaleLowerCase("en-US") === normalizedLower);
}

function extractClassAttribute(anchor: string): string {
  const match = anchor.match(/\bclass=(["'])([\s\S]*?)\1/iu);
  return match?.[2] ?? "";
}

function extractHref(anchor: string): string | undefined {
  const match = anchor.match(/\bhref=(["'])([\s\S]*?)\1/iu);
  return match?.[2];
}

function extractTagValue(html: string, tagName: string): string | undefined {
  const match = html.match(new RegExp(`<${tagName}[^>]*>([\\s\\S]*?)</${tagName}>`, "iu"));
  if (!match) {
    return undefined;
  }

  return normalizeWhitespace(decodeHtmlEntities(stripTags(match[1])));
}

function extractByClass(
  html: string,
  className: string,
): string | undefined {
  const directMatch = html.match(
    new RegExp(
      `<(span|p|div|h[1-6])\\b[^>]*class=(["'])[^"']*${escapeRegExp(className)}[^"']*\\2[^>]*>([\\s\\S]*?)<\\/\\1>`,
      "iu",
    ),
  );
  if (directMatch) {
    return normalizeWhitespace(decodeHtmlEntities(stripTags(directMatch[3])));
  }

  const matches = [...html.matchAll(/<(span|p|div|h[1-6])\b[^>]*class=(["'])([^"']*)\2[^>]*>([\s\S]*?)<\/\1>/giu)];
  for (const match of matches) {
    if (!hasClassToken(match[3], className)) {
      continue;
    }

    return normalizeWhitespace(decodeHtmlEntities(stripTags(match[4])));
  }

  return undefined;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function stripTags(value: string): string {
  return value.replace(/<[^>]+>/g, " ");
}

function normalizeArticleBody(
  bodyHtml: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): string {
  const rawLines = stripHtmlToLines(bodyHtml);
  const filteredLines = rawLines.filter((line) => !isNoiseLine(line, item));
  const bodyText = filteredLines.join("\n\n").trim();

  if (!bodyText) {
    throw new Error("Article body is empty after parsing.");
  }

  return bodyText;
}

function normalizeArticleUrl(value: string, baseUrl: string): string {
  const normalized = new URL(value, baseUrl);
  normalized.hash = "";
  normalized.search = "";

  if (!normalized.pathname.endsWith("/")) {
    normalized.pathname = `${normalized.pathname}/`;
  }

  return normalized.toString();
}
