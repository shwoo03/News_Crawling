import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import test from "node:test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runCycle } from "../src/app.ts";
import { Logger } from "../src/logger.ts";
import { DiscordNotifier } from "../src/services/discord.ts";
import { GroqSummarizer } from "../src/services/summarizer.ts";
import { extractArticleBody, parseRssItems } from "../src/sources/openai-news.ts";
import { SqliteStateStore } from "../src/storage/sqlite.ts";

test("parseRssItems reads RSS metadata and normalizes URLs", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "openai-news-rss.xml"), "utf8");
  const items = parseRssItems(fixture);

  assert.equal(items.length, 2);
  assert.equal(items[0]?.title, "Accelerating the next phase of AI");
  assert.equal(items[0]?.url, "https://openai.com/index/accelerating-the-next-phase-ai/");
  assert.equal(items[1]?.category, "B2B Story");
});

test("extractArticleBody keeps article text and removes author and share noise", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "openai-article.html"), "utf8");
  const body = extractArticleBody(fixture, {
    title: "OpenAI raises $122 billion to accelerate the next phase of AI",
    publishedAt: "2026-03-31T13:00:00.000Z",
    category: "Company",
  });

  assert.match(body, /Today, we closed our latest funding round/u);
  assert.match(body, /Deep conviction across global capital/u);
  assert.doesNotMatch(body, /Author/u);
  assert.doesNotMatch(body, /Share/u);
});

test("GroqSummarizer retries when the first summary exceeds the configured limit", async () => {
  let calls = 0;
  const fetchStub: typeof fetch = async () => {
    calls += 1;
    const content = calls === 1 ? "a".repeat(401) : "OpenAI의 새로운 요약은 핵심만 간결하게 정리합니다.";

    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              content,
            },
          },
        ],
      }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
        },
      },
    );
  };

  const summarizer = new GroqSummarizer("test-key", "test-model", 400, fetchStub);
  const summary = await summarizer.summarize({
    title: "테스트 제목",
    url: "https://example.com/article",
    bodyText: "테스트 본문",
  });

  assert.equal(calls, 2);
  assert.ok(summary.charCount <= 400);
});

test("GroqSummarizer formats long single-line summaries into readable lines", async () => {
  const fetchStub: typeof fetch = async () => {
    const content = [
      "최근 공개된 기사에서는 AI 계정 관리 서비스를 은행 고객에게 적용해 응답 속도가 0.5초로 개선되었고 만족도도 크게 향상되었다.",
      "복잡한 내부 규칙을 실시간으로 준수하면서 신뢰성 테스트를 거쳐 점진적 확장 전략을 사용했다.",
      "또한 초기에는 소규모 트래픽에서 시작해 확장 중이다.",
    ].join(" ");

    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              content,
            },
          },
        ],
      }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
        },
      },
    );
  };

  const summarizer = new GroqSummarizer("test-key", "test-model", 400, fetchStub);
  const summary = await summarizer.summarize({
    title: "테스트 기사 제목",
    url: "https://example.com/article",
    bodyText: "본문 텍스트",
  });

  const containsLineBreak = summary.summaryKo.includes("\n");
  assert.equal(containsLineBreak, true);
  assert.ok(summary.charCount <= 400);
});

test("SqliteStateStore prevents duplicate deliveries by remembering seen URLs", () => {
  const directory = mkdtempSync(join(tmpdir(), "news-crawling-"));
  const store = new SqliteStateStore(join(directory, "state.sqlite"));

  store.ensureSource({
    id: "openai-news",
    name: "OpenAI 뉴스",
    rssUrl: "https://openai.com/news/rss.xml",
  });

  assert.equal(store.hasSeen("openai-news", "https://openai.com/index/example/"), false);

  const articleId = store.markSeen({
    sourceId: "openai-news",
    title: "Example",
    url: "https://openai.com/index/example/",
    category: "Company",
    publishedAt: "2026-04-01T00:00:00.000Z",
  });

  store.recordDelivery({
    articleId,
    status: "sent",
    webhookTarget: "https://discord.com/api/webhooks/test",
  });

  assert.equal(store.hasSeen("openai-news", "https://openai.com/index/example/"), true);
  store.close();
});

test("runCycle bootstraps existing items without calling summary or Discord", async () => {
  const directory = mkdtempSync(join(tmpdir(), "news-crawling-"));
  const store = new SqliteStateStore(join(directory, "state.sqlite"));
  const source = {
    id: "openai-news",
    name: "OpenAI 뉴스",
    rssUrl: "https://openai.com/news/rss.xml",
    async listLatest() {
      return [
        {
          id: "https://openai.com/index/example/",
          title: "Example",
          url: "https://openai.com/index/example/",
          category: "Company",
          publishedAt: "2026-04-01T00:00:00.000Z",
        },
      ];
    },
    async fetchArticle() {
      throw new Error("fetchArticle should not run during bootstrap");
    },
  };

  const summarizer = new GroqSummarizer("test-key", "test-model", 400, async () => {
    throw new Error("summarizer should not run during bootstrap");
  });
  const notifier = new DiscordNotifier("https://discord.com/api/webhooks/test", async () => {
    throw new Error("notifier should not run during bootstrap");
  });

  await runCycle({
    logger: new Logger("error"),
    store,
    sources: [source],
    summarizer,
    notifier,
    webhookUrl: "https://discord.com/api/webhooks/test",
  });

  assert.equal(store.hasSeen("openai-news", "https://openai.com/index/example/"), true);
  store.close();
});
