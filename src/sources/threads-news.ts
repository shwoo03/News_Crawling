import type { ArticleContent, SourceAdapter, SourceListItem } from "../types.ts";
import { decodeHtmlEntities, normalizeWhitespace, stripHtmlToLines } from "../utils/text.ts";

const THREADS_PROFILE_URL = "https://www.threads.com/@choi.openai";
const THREAD_LIST_LIMIT = 10;

export class ThreadsNewsAdapter implements SourceAdapter {
  readonly id = "threads-news";
  readonly name = "Threads";
  readonly rssUrl = THREADS_PROFILE_URL;

  async listLatest(): Promise<SourceListItem[]> {
    const html = await fetchRenderedHtml(this.rssUrl);
    const items = parseThreadsList(html, this.rssUrl);
    if (items.length === 0) {
      throw new Error("No visible thread posts found");
    }

    return items.slice(0, THREAD_LIST_LIMIT);
  }

  async fetchArticle(item: SourceListItem): Promise<ArticleContent> {
    const html = await fetchRenderedHtml(item.url);
    const bodyText = extractThreadsArticleBody(html, item);

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

export function parseThreadsList(
  html: string,
  baseUrl = THREADS_PROFILE_URL,
): SourceListItem[] {
  const articleBlocks = extractArticleLikeBlocks(html);

  const parsed = articleBlocks
    .map((block) => parseThreadsListItem(block, baseUrl))
    .filter((item): item is SourceListItem => item !== undefined);

  if (parsed.length > 0) {
    return dedupeByUrl(parsed);
  }

  const fallback = fallbackParseFromAnchors(html, baseUrl);
  return dedupeByUrl(fallback);
}

export function extractThreadsArticleBody(
  html: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): string {
  const bodyMatch =
    matchFirst(
      html,
      /<div\b[^>]*class="[^"]*__body[^"]*"[^>]*>([\s\S]*?)<\/div>/iu,
    ) ??
    matchFirst(
      html,
      /<main\b[^>]*class="[^"]*post[^" ]*"[^>]*>([\s\S]*?)<\/main>/iu,
    ) ??
    matchFirst(html, /<article\b[^>]*>([\s\S]*?)<\/article>/iu) ??
    extractMetaDescription(html);

  if (!bodyMatch) {
    throw new Error("Article body container not found.");
  }

  const rawLines = stripHtmlToLines(bodyMatch[1]);
  const filtered = rawLines.filter((line) => !isThreadNoiseLine(line, item));
  const bodyText = filtered.join("\n\n").trim();

  if (!bodyText) {
    throw new Error("Article body is empty after parsing.");
  }

  return bodyText;
}

function extractMetaDescription(html: string): RegExpMatchArray | undefined {
  const metaCandidates = [
    /<meta\s+property=["']og:description["'][^>]*\s+content=(["'])([\s\S]*?)\1/iu,
    /<meta\s+name=["']description["'][^>]*\s+content=(["'])([\s\S]*?)\1/iu,
  ];

  for (const pattern of metaCandidates) {
    const match = matchFirst(html, pattern);
    if (match) {
      return {
        0: match[0],
        1: match[2],
        2: match[2],
      } as RegExpMatchArray;
  }
  }

  const ldJson = matchFirst(
    html,
    /<script\s+type=["']application\/ld\+json["'][\s\S]*?>([\s\S]*?)<\/script>/iu,
  );
  if (ldJson && ldJson[1]?.includes("articleBody")) {
    const articleBodyMatch = ldJson[1].match(/"articleBody"\s*:\s*"([\s\S]*?)"/u);
    if (articleBodyMatch) {
      return {
        0: ldJson[0],
        1: articleBodyMatch[1],
        2: articleBodyMatch[1],
      } as RegExpMatchArray;
    }
  }

  return undefined;
}

function parseThreadsListItem(
  block: string,
  baseUrl: string,
): SourceListItem | undefined {
  const link = extractThreadPostLink(block);
  if (!link) {
    return undefined;
  }

  const href = normalizeThreadUrl(link, baseUrl);
  const title = extractThreadTitle(block, link) || fallbackThreadTitleFromHref(link);

  const dateText = extractDateText(block);
  if (!dateText) {
    return undefined;
  }

  const parsedDate = new Date(dateText);
  if (Number.isNaN(parsedDate.getTime())) {
    return undefined;
  }

  const category =
    extractByClassName(block, "subject") ??
    extractByClassName(block, "topic") ??
    extractByClassName(block, "category") ??
    "Posts";

  return {
    id: href,
    title,
    url: href,
    publishedAt: parsedDate.toISOString(),
    category,
  };
}

function extractThreadTitle(block: string, href: string): string {
  const anchorPattern = /<a\b[^>]*href=(["'])([^"']+)\1[^>]*>([\s\S]*?)<\/a>/gi;
  const normalizedHref = normalizeThreadUrl(href, THREADS_PROFILE_URL);
  const anchorMatch = [...block.matchAll(anchorPattern)]
    .map((match) => ({ href: match[2], html: match[3] }))
    .find((row) => {
      const normalizedAnchor = normalizeThreadUrl(row.href, THREADS_PROFILE_URL);
      return normalizedAnchor === normalizedHref || row.href === href;
    });

  const sourceHtml = anchorMatch?.html ?? block;

  const headingMatch = sourceHtml.match(/<(h[1-6])\b[^>]*>([\s\S]*?)<\/\1>/i);
  if (headingMatch?.[2]) {
    const heading = normalizeWhitespace(decodeHtmlEntities(stripTags(headingMatch[2])));
    if (heading) {
      return heading;
    }
  }

  const titleByClass = extractByClassName(sourceHtml, "title");
  if (titleByClass) {
    return titleByClass;
  }

  const paragraphMatch = sourceHtml.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i);
  if (paragraphMatch?.[1]) {
    const paragraphTitle = normalizeWhitespace(decodeHtmlEntities(stripTags(paragraphMatch[1])));
    if (paragraphTitle) {
      return paragraphTitle;
    }
  }

  const fallback = normalizeWhitespace(decodeHtmlEntities(stripTags(sourceHtml)));
  if (!fallback) {
    return "";
  }

  const lines = fallback
    .split(/[\r\n]+/u)
    .map((line) => normalizeWhitespace(line))
    .filter(Boolean);

  for (const line of lines) {
    if (looksLikeDateOrNoise(line)) {
      continue;
    }

    return line;
  }

  return "";
}

function extractArticleLikeBlocks(html: string): string[] {
  const articleBlocks = [...html.matchAll(/<article\b[^>]*>[\s\S]*?<\/article>/giu)];
  if (articleBlocks.length > 0) {
    return articleBlocks.map((match) => match[0]);
  }

  const postAnchors = [...html.matchAll(/<a\b[^>]*\bhref=(["'])([^"']+)\1[^>]*>([\s\S]*?)<\/a>/giu)]
    .filter((match) => isThreadPostHref(match[2]))
    .slice(0, THREAD_LIST_LIMIT * 3)
    .map((match) => match[0]);

  return postAnchors;
}

function fallbackParseFromAnchors(
  html: string,
  baseUrl: string,
): SourceListItem[] {
  const anchors = [...html.matchAll(/<a\b[^>]*\bhref=(["'])([^"']+)\1[^>]*>([\s\S]*?)<\/a>/giu)];
  const items: SourceListItem[] = [];

  for (const [, , href, anchorHtml] of anchors) {
    if (!isThreadPostHref(href)) {
      continue;
    }

    const normalized = normalizeThreadUrl(href, baseUrl);
    const title =
      extractThreadTitle(`<a href="${href}">${anchorHtml}</a>`, href) || fallbackThreadTitleFromHref(href);
    if (!title) {
      continue;
    }

    const dateText = extractDateText(anchorHtml);
    if (!dateText) {
      continue;
    }

    const parsedDate = new Date(dateText);
    if (Number.isNaN(parsedDate.getTime())) {
      continue;
    }

    const category =
      extractByClassName(anchorHtml, "subject") ??
      extractByClassName(anchorHtml, "topic") ??
      extractByClassName(anchorHtml, "category") ??
      "Posts";

    items.push({
      id: normalized,
      title,
      url: normalized,
      publishedAt: parsedDate.toISOString(),
      category,
    });
  }

  return items.slice(0, THREAD_LIST_LIMIT);
}

function extractThreadPostLink(block: string): string | undefined {
  const anchors = [...block.matchAll(/<a\b[^>]*\bhref=(["'])([^"']+)\1[^>]*>/giu)];
  for (const [, , href] of anchors) {
    if (isThreadPostHref(href)) {
      return href;
    }
  }

  return undefined;
}

function isThreadPostHref(href: string): boolean {
  const normalized = href.trim().toLowerCase();
  return normalized.startsWith("/post/") || normalized.includes("/post/") || normalized.startsWith("/threads/");
}

function fallbackThreadTitleFromHref(href: string): string {
  const path = normalizeThreadUrl(href, THREADS_PROFILE_URL)
    .replace(/^https?:\/\/[^/]+\//u, "")
    .replace(/\/$/u, "");
  const token = path.split("/").at(-1) ?? "Threads post";

  return `Thread post ${token}`;
}

function extractDateText(html: string): string {
  const timeTag = matchFirst(html, /<time\b[^>]*>([\s\S]*?)<\/time>/iu);
  if (timeTag) {
    const textDate = decodeHtmlEntities(normalizeWhitespace(stripTags(timeTag[1])));
    if (textDate) {
      if (!Number.isNaN(new Date(textDate).getTime())) {
        return textDate;
      }
    }
  }

  const timeDateTime = matchFirst(html, /<time\b[^>]*datetime=(["'])(.*?)\1/iu);
  if (timeDateTime) {
    return decodeHtmlEntities(normalizeWhitespace(timeDateTime[2]));
  }

  const monthDate = html.match(
    /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}\b/iu,
  );
  if (monthDate) {
    return monthDate[0];
  }

  const ymd = html.match(/\b\d{4}-\d{2}-\d{2}T[^\s<]+/u);
  if (ymd) {
    return ymd[0];
  }

  return "";
}

function looksLikeDateOrNoise(value: string): boolean {
  const normalized = normalizeWhitespace(value).toLocaleLowerCase("en-US");
  if (!normalized) {
    return true;
  }

  return Boolean(
    normalized.match(
      /\b\d{1,2}\s+(?:hours?|mins?|days?)\s+ago\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|^\d{1,3}[smhdwy]$/iu,
    ),
  );
}

function extractByClassName(block: string, className: string): string | undefined {
  const pattern = new RegExp(
    `<[^>]*class=(["'])[^"']*${className}[^"']*\\1[^>]*>([\s\S]*?)</[^>]+>`,
    "iu",
  );
  const match = block.match(pattern);
  if (!match) {
    return undefined;
  }

  return normalizeWhitespace(decodeHtmlEntities(stripTags(match[2])));
}

function normalizeThreadUrl(value: string, baseUrl: string): string {
  const url = new URL(value, baseUrl);
  url.hash = "";
  url.search = "";

  if (!url.pathname.endsWith("/")) {
    url.pathname = `${url.pathname}/`;
  }

  return url.toString();
}

function isThreadNoiseLine(
  line: string,
  item: Pick<SourceListItem, "title" | "publishedAt" | "category">,
): boolean {
  const normalized = normalizeWhitespace(line).toLocaleLowerCase("en-US");
  const publishedDate = new Date(item.publishedAt).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).toLocaleLowerCase("en-US");

  const alternatePublishedDate = new Date(item.publishedAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  return [
    "share",
    "share on",
    "copy link",
    "reply",
    "more",
    "menu",
    "follow",
    "view replies",
    "like",
    "comment",
    "repost",
    "menu",
    item.title,
    item.category,
    publishedDate,
    alternatePublishedDate,
  ]
    .filter(Boolean)
    .map((value) => String(value).toLocaleLowerCase("en-US"))
    .some((noise) => {
      if (normalized.startsWith(noise) || normalized === noise) {
        return true;
      }

      if (normalized.match(/\b\d{1,2},\s*\d{4}\b/u)) {
        return /\b\d{1,2},\s*\d{4}\b/u.test(normalized);
      }

      return false;
    });
}

function dedupeByUrl(items: SourceListItem[]): SourceListItem[] {
  const seen = new Set<string>();
  const unique: SourceListItem[] = [];
  for (const item of items) {
    if (seen.has(item.url)) {
      continue;
    }

    seen.add(item.url);
    unique.push(item);
  }

  return unique;
}

function stripTags(value: string): string {
  return value.replace(/<[^>]+>/gu, " ");
}

function matchFirst(html: string, pattern: RegExp): RegExpMatchArray | undefined {
  const match = html.match(pattern);
  return match ?? undefined;
}

async function fetchRenderedHtml(url: string): Promise<string> {
  let browser: { close: () => Promise<void> } | undefined;
  let page:
    | {
      close: () => Promise<void>;
      goto: (url: string, options: { waitUntil: string; timeout: number }) => Promise<void>;
      waitForLoadState: (state: string, options: { timeout: number }) => Promise<void>;
      waitForTimeout: (ms: number) => Promise<void>;
      content: () => Promise<string>;
    }
    | undefined;

  try {
    const { chromium } = await loadPlaywright();

    browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    page = await browser.newPage({
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    });
    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page
      .waitForLoadState("networkidle", {
        timeout: 15_000,
      })
      .catch(() => undefined);

    await page.waitForTimeout(1_200).catch(() => undefined);
    return await page.content();
  } finally {
    if (page) {
      await page.close().catch(() => undefined);
    }
    if (browser) {
      await browser.close().catch(() => undefined);
    }
  }
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    const cause = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Playwright runtime is not available. Install it with \`npm install\` and run \`npx playwright install\`. Original error: ${cause}`,
    );
  }
}
