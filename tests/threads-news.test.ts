import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import test from "node:test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runCycle } from "../src/app.ts";
import { Logger } from "../src/logger.ts";
import { DiscordNotifier } from "../src/services/discord.ts";
import { GroqSummarizer } from "../src/services/summarizer.ts";
import { extractThreadsArticleBody, parseThreadsList } from "../src/sources/threads-news.ts";
import { SqliteStateStore } from "../src/storage/sqlite.ts";

test("parseThreadsList reads top posts and normalizes URLs", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "threads-list.html"), "utf8");
  const items = parseThreadsList(fixture);

  assert.equal(items.length, 10);
  assert.equal(items[0]?.url, "https://www.threads.com/@choi.openai/post/1001/the-ai-sprint-update/");
  assert.equal(items[0]?.title, "The AI Sprint update everyone needed");
  assert.equal(items[0]?.category, "Posts");
  assert.equal(items[0]?.publishedAt, new Date("Apr 1, 2026").toISOString());
  assert.equal(items[9]?.url, "https://www.threads.com/post/1010/");
  for (const item of items) {
    assert.equal(item.url.endsWith("/"), true);
  }
});

test("extractThreadsArticleBody keeps thread text and removes share/menu noise", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "threads-article.html"), "utf8");
  const body = extractThreadsArticleBody(fixture, {
    title: "The AI Sprint update everyone needed",
    publishedAt: "2026-04-01T09:00:00.000Z",
    category: "Posts",
  });

  assert.match(body, /This is the first paragraph we want to summarize\./);
  assert.match(body, /Here is the second important sentence with details\./);
  assert.match(body, /And a third one to make sure extraction keeps multiple lines\./);
  assert.doesNotMatch(body, /Share on Twitter/u);
  assert.doesNotMatch(body, /Share on LinkedIn/u);
  assert.doesNotMatch(body, /^Share$/mu);
  assert.doesNotMatch(body, /Like/);
  assert.doesNotMatch(body, /Comment/);
  assert.doesNotMatch(body, /Menu/);
});

test("extractThreadsArticleBody throws when no body can be extracted", () => {
  const fixture = readFileSync(
    join(import.meta.dirname, "fixtures", "threads-article-empty-body.html"),
    "utf8",
  );

  assert.throws(
    () =>
      extractThreadsArticleBody(fixture, {
        title: "Empty example",
        publishedAt: "2026-04-01T00:00:00.000Z",
        category: "Posts",
      }),
    { message: "Article body is empty after parsing." },
  );
});

test("runCycle bootstrap then process one new thread post only once", async () => {
  const directory = mkdtempSync(join(tmpdir(), "news-crawling-"));
  const store = new SqliteStateStore(join(directory, "state.sqlite"));
  const sourceId = "threads-news";
  const firstSeen = {
    id: "https://www.threads.com/@choi.openai/post/1001/the-ai-sprint-update/",
    title: "The AI Sprint update everyone needed",
    url: "https://www.threads.com/@choi.openai/post/1001/the-ai-sprint-update/",
    category: "Posts",
    publishedAt: new Date("2026-04-01T09:00:00.000Z").toISOString(),
  };
  const newPost = {
    id: "https://www.threads.com/@choi.openai/post/1002/openai-update/",
    title: "OpenAI and Threads roadmap note",
    url: "https://www.threads.com/@choi.openai/post/1002/openai-update/",
    category: "Posts",
    publishedAt: new Date("2026-04-02T09:00:00.000Z").toISOString(),
  };

  let runCount = 0;
  let fetchCount = 0;
  const source = {
    id: sourceId,
    name: "Threads",
    rssUrl: "https://www.threads.com/@choi.openai",
    async listLatest() {
      runCount += 1;
      if (runCount === 1) {
        return [firstSeen];
      }

      return [newPost, firstSeen];
    },
    async fetchArticle(item: { title: string; url: string; publishedAt: string; category: string }) {
      if (item.url !== newPost.url) {
        throw new Error("fetchArticle should only run for new post in this test");
      }

      fetchCount += 1;
      return {
        sourceId,
        sourceName: "Threads",
        title: item.title,
        url: item.url,
        publishedAt: item.publishedAt,
        category: item.category,
        bodyText: "Thread body summary target",
      };
    },
  };

  const summarizer = new GroqSummarizer(
    "test-key",
    ["test-model"],
    400,
    async () => {
      return new Response(
        JSON.stringify({
          choices: [{
            message: {
              content: "요약 결과",
            },
          }],
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        },
      );
    },
  );

  let deliveryCount = 0;
  const notifier = new DiscordNotifier("https://discord.com/api/webhooks/test", async () => {
    deliveryCount += 1;
    return new Response("", { status: 200 });
  });

  await runCycle({
    logger: new Logger("error"),
    store,
    sources: [source],
    summarizer,
    notifier,
    webhookUrl: "https://discord.com/api/webhooks/test",
  });

  assert.equal(store.hasSeen(sourceId, firstSeen.url), true);
  assert.equal(store.hasSeen(sourceId, newPost.url), false);
  assert.equal(fetchCount, 0);
  assert.equal(deliveryCount, 0);

  await runCycle({
    logger: new Logger("error"),
    store,
    sources: [source],
    summarizer,
    notifier,
    webhookUrl: "https://discord.com/api/webhooks/test",
  });

  assert.equal(store.hasSeen(sourceId, newPost.url), true);
  assert.equal(fetchCount, 1);
  assert.equal(deliveryCount, 1);

  await runCycle({
    logger: new Logger("error"),
    store,
    sources: [source],
    summarizer,
    notifier,
    webhookUrl: "https://discord.com/api/webhooks/test",
  });

  assert.equal(fetchCount, 1);
  assert.equal(deliveryCount, 1);
  store.close();
});
