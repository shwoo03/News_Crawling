import { setTimeout as delay } from "node:timers/promises";
import type { SourceListItem } from "./types.ts";
import type { AppConfig } from "./config.ts";
import { Logger } from "./logger.ts";
import { DiscordNotifier } from "./services/discord.ts";
import { GroqSummarizer } from "./services/summarizer.ts";
import { OpenAINewsAdapter } from "./sources/openai-news.ts";
import { AnthropicNewsAdapter } from "./sources/anthropic-news.ts";
import { ThreadsNewsAdapter } from "./sources/threads-news.ts";
import { SqliteStateStore } from "./storage/sqlite.ts";
import type { SourceAdapter } from "./types.ts";

const ROUTE_TICK_MS = 30_000;

export function buildSourceAdapters(): SourceAdapter[] {
  return [
    new OpenAINewsAdapter(),
    new AnthropicNewsAdapter(),
    new ThreadsNewsAdapter(),
  ];
}

export function resolveGroqApiKey(
  store: SqliteStateStore,
  envKey: string | undefined,
): string | undefined {
  const stored = store.getSetting("groq_api_key")?.trim();
  if (stored) {
    return stored;
  }

  return envKey?.trim() || undefined;
}

export async function runWorker(config: AppConfig): Promise<void> {
  const logger = new Logger(config.logLevel, config.logFormat);
  const store = new SqliteStateStore(config.sqlitePath);
  const sources = buildSourceAdapters();
  for (const source of sources) {
    store.ensureSource(source);
  }

  process.on("SIGINT", () => {
    store.close();
    process.exit(0);
  });

  process.on("SIGTERM", () => {
    store.close();
    process.exit(0);
  });

  logger.info("Worker started.", {
    tickIntervalSeconds: ROUTE_TICK_MS / 1000,
    sources: sources.map((source) => source.id),
  });

  for (;;) {
    try {
      await tickRoutes({ logger, store, sources, config });
    } catch (error) {
      logger.error("Worker tick failed.", {
        error: error instanceof Error ? error.message : String(error),
      });
    }
    await delay(ROUTE_TICK_MS);
  }
}

async function tickRoutes(input: {
  logger: Logger;
  store: SqliteStateStore;
  sources: SourceAdapter[];
  config: AppConfig;
}): Promise<void> {
  const { logger, store, sources, config } = input;
  const routes = store.listRoutes().filter((route) => route.enabled);
  if (routes.length === 0) {
    return;
  }

  const groqApiKey = resolveGroqApiKey(store, config.groqApiKey);
  if (!groqApiKey) {
    logger.warn("Groq API key is not configured. Routes will be skipped this tick.");
    return;
  }

  const summarizer = new GroqSummarizer(
    groqApiKey,
    config.groqModels,
    config.summaryMaxCharacters,
  );

  const sourceMap = new Map(sources.map((source) => [source.id, source] as const));
  const now = Date.now();

  for (const route of routes) {
    const dueAt = route.lastRunAt ? Date.parse(route.lastRunAt) : 0;
    const intervalMs = route.pollIntervalMinutes * 60_000;
    if (route.lastRunAt && now - dueAt < intervalMs) {
      continue;
    }

    const source = sourceMap.get(route.sourceId);
    if (!source) {
      logger.warn("Route references unknown source. Skipping.", {
        routeId: route.id,
        sourceId: route.sourceId,
      });
      continue;
    }

    const webhook = store.getWebhook(route.webhookId);
    if (!webhook) {
      logger.warn("Route references missing webhook. Skipping.", {
        routeId: route.id,
        webhookId: route.webhookId,
      });
      continue;
    }

    try {
      await runRouteCycle({
        logger,
        store,
        source,
        summarizer,
        notifier: new DiscordNotifier(webhook.url),
        webhookUrl: webhook.url,
        routeId: route.id,
      });
      store.markRouteRun(route.id);
    } catch (error) {
      logger.error("Route cycle failed.", {
        routeId: route.id,
        sourceId: route.sourceId,
        webhookId: route.webhookId,
        error: error instanceof Error ? error.message : String(error),
      });
      store.markRouteRun(route.id);
    }
  }
}

async function runRouteCycle(input: {
  logger: Logger;
  store: SqliteStateStore;
  source: SourceAdapter;
  summarizer: GroqSummarizer;
  notifier: DiscordNotifier;
  webhookUrl: string;
  routeId: number;
}): Promise<void> {
  const { logger, store, source, summarizer, notifier, webhookUrl, routeId } = input;

  store.ensureSource(source);
  logger.info("Checking route.", {
    routeId,
    sourceId: source.id,
    rssUrl: source.rssUrl,
  });

  const items = sortByPublishedDesc(await source.listLatest());

  if (store.countArticlesForSource(source.id) === 0) {
    for (const item of items) {
      store.markSeen({
        sourceId: source.id,
        title: item.title,
        url: item.url,
        publishedAt: item.publishedAt,
        category: item.category,
      });
    }

    logger.info("Initial bootstrap completed for source.", {
      routeId,
      sourceId: source.id,
      seededCount: items.length,
    });
    return;
  }

  for (const item of items) {
    if (store.hasSeen(source.id, item.url)) {
      continue;
    }

    logger.info("New article detected.", {
      routeId,
      sourceId: source.id,
      url: item.url,
    });

    const articleId = store.markSeen({
      sourceId: source.id,
      title: item.title,
      url: item.url,
      publishedAt: item.publishedAt,
      category: item.category,
    });

    try {
      const article = await source.fetchArticle(item);
      const summary = await summarizer.summarize(article);
      const delivery = await notifier.send(article, summary);

      store.recordDelivery({
        articleId,
        status: delivery.status,
        webhookTarget: webhookUrl,
        errorMessage: delivery.status === "skipped" ? delivery.reason : undefined,
      });

      logger.info("Article processed.", {
        routeId,
        sourceId: source.id,
        url: item.url,
        deliveryStatus: delivery.status,
        summaryLength: summary.charCount,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      store.recordDelivery({
        articleId,
        status: "failed",
        webhookTarget: webhookUrl,
        errorMessage: message,
      });

      logger.error("Article processing failed.", {
        routeId,
        sourceId: source.id,
        url: item.url,
        error: message,
      });
    }
  }
}

export async function runTopArticleTest(
  config: AppConfig,
  articleCount: number,
  focusUrl?: string,
): Promise<void> {
  const logger = new Logger(config.logLevel, config.logFormat);
  const store = new SqliteStateStore(config.sqlitePath);
  const sources = buildSourceAdapters();
  const groqApiKey = resolveGroqApiKey(store, config.groqApiKey);
  if (!groqApiKey) {
    throw new Error(
      "Groq API key is not configured. Set it in the dashboard or via GROQ_API_KEY.",
    );
  }

  const summarizer = new GroqSummarizer(
    groqApiKey,
    config.groqModels,
    config.summaryMaxCharacters,
  );

  const webhooks = store.listWebhooks();
  const firstWebhookUrl = webhooks[0]?.url;
  logger.info("Top test webhook target.", {
    webhook: summarizeWebhook(firstWebhookUrl),
  });

  logger.info("Running top article test.", {
    sourceCount: sources.length,
    requestedCount: articleCount,
  });

  for (const source of sources) {
    logger.info("Top article test source.", {
      sourceId: source.id,
      sourceName: source.name,
    });

    const items = sortByPublishedDesc(await source.listLatest());
    if (items.length === 0) {
      logger.warn("No items found in feed for test mode.", {
        sourceId: source.id,
      });
      continue;
    }

    const selected = pickTopItems(items, articleCount, focusUrl);
    logger.info("Top article test selected items.", {
      sourceId: source.id,
      totalItems: items.length,
      selectedCount: selected.length,
      urls: selected.map((item) => item.url),
    });
    if (selected.length === 0) {
      logger.warn("No items available after sort/filter for test mode.", {
        sourceId: source.id,
      });
      continue;
    }

    for (const [index, item] of selected.entries()) {
      try {
        const article = await source.fetchArticle(item);
        const summary = await summarizer.summarize(article);
        const delivery = await new DiscordNotifier(firstWebhookUrl).send(article, summary);

        logger.info("Top article test processed.", {
          sourceId: source.id,
          index: index + 1,
          title: article.title,
          url: article.url,
          deliveryStatus: delivery.status,
          summaryLength: summary.charCount,
        });
        if (delivery.status === "skipped") {
          logger.warn("Discord webhook is missing. Add a webhook in the dashboard to enable delivery.");
        }
      } catch (error) {
        logger.error("Top article test failed for item.", {
          sourceId: source.id,
          index: index + 1,
          url: item.url,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
  }

  store.close();
}

function summarizeWebhook(value: string | undefined): string {
  if (!value) {
    return "missing";
  }

  try {
    const url = new URL(value);
    const parts = url.pathname.split("/");
    const webhookId = parts[3] ?? "";
    const maskedToken = parts[4] ? `${parts[4].slice(0, 8)}...` : "";

    return `${url.hostname}/${webhookId}/${maskedToken}`;
  } catch {
    return "invalid-url";
  }
}

function pickTopItems(items: SourceListItem[], count: number, focusUrl?: string): SourceListItem[] {
  if (count <= 0) {
    return [];
  }

  const topItems = items.slice(0, count);

  if (!focusUrl) {
    return topItems;
  }

  const normalizedFocus = normalizeCanonicalUrl(focusUrl);
  const focusedIndex = items.findIndex((item) => normalizeCanonicalUrl(item.url) === normalizedFocus);
  if (focusedIndex < 0) {
    return topItems;
  }

  const focused = items[focusedIndex];
  const focusedCanonical = normalizeCanonicalUrl(focused.url);
  const rest = items.filter((item) => normalizeCanonicalUrl(item.url) !== focusedCanonical);
  return [focused, ...rest].slice(0, count);
}

export function sortByPublishedDesc(items: SourceListItem[]): SourceListItem[] {
  return [...items].sort((left, right) => right.publishedAt.localeCompare(left.publishedAt));
}

function normalizeCanonicalUrl(value: string): string {
  const url = new URL(value);
  url.hash = "";
  url.search = "";
  if (!url.pathname.endsWith("/")) {
    url.pathname = `${url.pathname}/`;
  }

  return url.toString();
}

export async function runCycle(input: {
  logger: Logger;
  store: SqliteStateStore;
  sources: SourceAdapter[];
  summarizer: GroqSummarizer;
  notifier: DiscordNotifier;
  webhookUrl: string | undefined;
}): Promise<void> {
  for (const source of input.sources) {
    try {
      input.store.ensureSource(source);
      input.logger.info("Checking source.", { sourceId: source.id, rssUrl: source.rssUrl });

      const items = sortByPublishedDesc(await source.listLatest());

      if (input.store.countArticlesForSource(source.id) === 0) {
        for (const item of items) {
          input.store.markSeen({
            sourceId: source.id,
            title: item.title,
            url: item.url,
            publishedAt: item.publishedAt,
            category: item.category,
          });
        }

        input.logger.info("Initial bootstrap completed. Existing articles were marked as seen without delivery.", {
          sourceId: source.id,
          seededCount: items.length,
        });
        continue;
      }

      for (const item of items) {
        if (input.store.hasSeen(source.id, item.url)) {
          continue;
        }

        input.logger.info("New article detected.", {
          sourceId: source.id,
          url: item.url,
        });

        const articleId = input.store.markSeen({
          sourceId: source.id,
          title: item.title,
          url: item.url,
          publishedAt: item.publishedAt,
          category: item.category,
        });

        try {
          const article = await source.fetchArticle(item);
          const summary = await input.summarizer.summarize(article);
          const delivery = await input.notifier.send(article, summary);

          input.store.recordDelivery({
            articleId,
            status: delivery.status,
            webhookTarget: input.webhookUrl ?? null,
            errorMessage: delivery.status === "skipped" ? delivery.reason : undefined,
          });

          input.logger.info("Article processed.", {
            sourceId: source.id,
            url: item.url,
            deliveryStatus: delivery.status,
            summaryLength: summary.charCount,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          input.store.recordDelivery({
            articleId,
            status: "failed",
            webhookTarget: input.webhookUrl ?? null,
            errorMessage: message,
          });

          input.logger.error("Article processing failed.", {
            sourceId: source.id,
            url: item.url,
            error: message,
          });
        }
      }
    } catch (error) {
      input.logger.error("Source processing failed.", {
        sourceId: source.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
}
