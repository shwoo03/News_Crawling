import type { ArticleContent, FetchLike, SourceAdapter, SourceListItem } from "../types.ts";
import { fetchText } from "../utils/http.ts";
import { normalizeWhitespace, stripHtmlToLines } from "../utils/text.ts";

const RSS_URL = "https://openai.com/news/rss.xml";

export class OpenAINewsAdapter implements SourceAdapter {
  readonly id = "openai-news";
  readonly name = "OpenAI 뉴스";
  readonly rssUrl = RSS_URL;

  constructor(private readonly fetchImpl: FetchLike = fetch) {}

  async listLatest(): Promise<SourceListItem[]> {
    const xml = await fetchText(this.rssUrl, undefined, this.fetchImpl);
    return parseRssItems(xml);
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

export function parseRssItems(xml: string): SourceListItem[] {
  const items = xml.match(/<item>[\s\S]*?<\/item>/gu) ?? [];
  return items.map((itemXml) => {
    const rawUrl = extractTagValue(itemXml, "link");
    const normalizedUrl = normalizeArticleUrl(rawUrl);

    return {
      id: normalizedUrl,
      title: extractTagValue(itemXml, "title"),
      url: normalizedUrl,
      publishedAt: new Date(extractTagValue(itemXml, "pubDate")).toISOString(),
      category: extractOptionalTagValue(itemXml, "category") || "Uncategorized",
    };
  });
}

export function extractArticleBody(
  html: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): string {
  const titleIndex = html.indexOf("<h1");
  if (titleIndex < 0) {
    throw new Error("Article title block not found.");
  }

  const firstParagraphIndex = html.indexOf("<p", titleIndex);
  if (firstParagraphIndex < 0) {
    throw new Error("Article paragraph block not found.");
  }

  const authorIndex = findFirstMarker(html, [">Author<", "Author</h2>"], firstParagraphIndex);
  const keepReadingIndex = findFirstMarker(html, [">Keep reading<", "Keep reading</h2>"], firstParagraphIndex);
  const endIndex = [authorIndex, keepReadingIndex]
    .filter((value) => value > firstParagraphIndex)
    .sort((left, right) => left - right)[0];

  if (!endIndex) {
    throw new Error("Article end marker not found.");
  }

  const fragment = html.slice(firstParagraphIndex, endIndex);
  const rawLines = stripHtmlToLines(fragment);
  const filteredLines = rawLines.filter((line) => !isNoiseLine(line, item));
  const bodyText = filteredLines.join("\n\n").trim();

  if (!bodyText) {
    throw new Error("Article body is empty after parsing.");
  }

  return bodyText;
}

function extractTagValue(xml: string, tagName: string): string {
  const value = extractOptionalTagValue(xml, tagName);
  if (value) {
    return value;
  }

  throw new Error(`Missing <${tagName}> in RSS item.`);
}

function extractOptionalTagValue(xml: string, tagName: string): string | undefined {
  const cdataMatch = xml.match(new RegExp(`<${tagName}><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tagName}>`, "iu"));
  if (cdataMatch) {
    return normalizeWhitespace(cdataMatch[1]);
  }

  const plainMatch = xml.match(new RegExp(`<${tagName}>([\\s\\S]*?)<\\/${tagName}>`, "iu"));
  if (!plainMatch) {
    return undefined;
  }

  return normalizeWhitespace(plainMatch[1]);
}

function normalizeArticleUrl(value: string): string {
  const url = new URL(value);
  url.hash = "";
  url.search = "";
  if (!url.pathname.endsWith("/")) {
    url.pathname = `${url.pathname}/`;
  }

  return url.toString();
}

function findFirstMarker(html: string, markers: string[], fromIndex: number): number {
  const indices = markers
    .map((marker) => html.indexOf(marker, fromIndex))
    .filter((index) => index >= 0)
    .sort((left, right) => left - right);

  return indices[0] ?? -1;
}

function isNoiseLine(line: string, item: Pick<SourceListItem, "title" | "publishedAt" | "category">): boolean {
  const normalizedLine = normalizeWhitespace(line);
  const publishedDate = new Date(item.publishedAt).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  return [
    "Share",
    "Author",
    "OpenAI",
    "Start building",
    "Loading...",
    "Loading…",
    "Results",
    item.title,
    item.category,
    publishedDate,
  ].includes(normalizedLine) || /^(Company size|Region|Industry|Products):/u.test(normalizedLine);
}
