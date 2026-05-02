export type LogLevel = "debug" | "info" | "warn" | "error";
export type LogFormat = "json" | "pretty";

export type SourceListItem = {
  id: string;
  title: string;
  url: string;
  publishedAt: string;
  category: string;
};

export type ArticleContent = {
  sourceId: string;
  sourceName: string;
  title: string;
  url: string;
  publishedAt: string;
  category: string;
  bodyText: string;
};

export type SummaryBriefing = {
  lead: string;
  summary: string[];
  highlights: string[];
  importance: string[];
};

export type SummaryResult = {
  summaryKo: string;
  charCount: number;
  briefing: SummaryBriefing;
};

export type DiscordDeliveryResult =
  | { status: "sent" }
  | { status: "skipped"; reason: string };

export type SourceAdapter = {
  readonly id: string;
  readonly name: string;
  readonly rssUrl: string;
  listLatest(): Promise<SourceListItem[]>;
  fetchArticle(item: SourceListItem): Promise<ArticleContent>;
};

export type FetchLike = typeof fetch;
