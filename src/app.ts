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

export async function runWorker(config: AppConfig): Promise<void> {
  const logger = new Logger(config.logLevel, config.logFormat);
  const store = new SqliteStateStore(config.sqlitePath);
  const sources: SourceAdapter[] = [
    new OpenAINewsAdapter(),
    new AnthropicNewsAdapter(),
    new ThreadsNewsAdapter(),
  ];
  const summarizer = new GroqSummarizer(
    config.groqApiKey,
    config.groqModels,
    config.summaryMaxCharacters,
  );
  const webhookUrl = config.discordWebhookUrl;
  const notifier = new DiscordNotifier(webhookUrl);

  if (!webhookUrl) {
    logger.warn("Discord webhook is not configured. Top-level delivery is skipped.");
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
    pollIntervalMinutes: config.pollIntervalMinutes,
    sources: sources.map((source) => source.id),
  });

  try {
    for (;;) {
      try {
        await runCycle({ logger, store, sources, summarizer, notifier, webhookUrl });
      } catch (error) {
        logger.error("Worker cycle failed.", {
          error: error instanceof Error ? error.message : String(error),
        });
      }
      await delay(config.pollIntervalMinutes * 60_000);
    }
  } finally {
    store.close();
  }
}

export async function runTopArticleTest(
  config: AppConfig,
  articleCount: number,
  focusUrl?: string,
): Promise<void> {
  const logger = new Logger(config.logLevel, config.logFormat);
  const sources: SourceAdapter[] = [
    new OpenAINewsAdapter(),
    new AnthropicNewsAdapter(),
    new ThreadsNewsAdapter(),
  ];
  const summarizer = new GroqSummarizer(
    config.groqApiKey,
    config.groqModels,
    config.summaryMaxCharacters,
  );
  const webhookUrl = config.discordWebhookUrl;

  logger.info("Top test webhook target.", {
    webhook: summarizeWebhook(webhookUrl),
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
        const delivery = await notifierFromUrl(webhookUrl).send(article, summary);

        logger.info("Top article test processed.", {
          sourceId: source.id,
          index: index + 1,
          title: article.title,
          url: article.url,
          deliveryStatus: delivery.status,
          summaryLength: summary.charCount,
        });
        if (delivery.status === "skipped") {
          logger.warn("Discord webhook is missing. Set DISCORD_WEBHOOK_URL to enable delivery.");
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
}

function notifierFromUrl(webhookUrl: string | undefined): DiscordNotifier {
  return new DiscordNotifier(webhookUrl);
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
