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

function briefingContent(overrides: Partial<{
  lead: string;
  summary: string[];
  highlights: string[];
  importance: string[];
}> = {}): string {
  return JSON.stringify({
    lead: overrides.lead ?? "오픈AI가 새로운 계정 보안 기능을 공개했습니다.",
    summary: overrides.summary ?? [
      "새 기능은 계정 보호를 강화하고 조직 관리자가 위험을 더 빨리 파악하게 돕습니다.",
      "사용자는 추가 인증과 관리 기능을 통해 민감한 작업을 더 안전하게 처리할 수 있습니다.",
      "오픈AI는 기업 환경에서 AI 사용이 늘어나는 흐름에 맞춰 보안 운영 기능을 확장했습니다.",
    ],
    highlights: overrides.highlights ?? [
      "고급 계정 보안 기능 공개",
      "조직 관리자용 위험 관리 강화",
      "민감한 작업 보호 절차 추가",
      "기업 사용자를 위한 보안 운영 개선",
      "업무용 AI 계정 관리 기준 제시",
    ],
    importance: overrides.importance ?? [
      "AI 도구가 업무 핵심 시스템이 되면서 계정 보안이 운영 리스크와 직접 연결됩니다.",
      "관리 기능 강화는 기업의 AI 도입 장벽을 낮추는 실무 요건입니다.",
      "보안 통제가 명확해질수록 조직은 AI 도구를 더 넓은 업무에 적용할 수 있습니다.",
    ],
  });
}

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
    const content = calls === 1
      ? briefingContent({ lead: "a".repeat(651) })
      : briefingContent();

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

  const summarizer = new GroqSummarizer("test-key", ["test-model"], 650, fetchStub);
  const summary = await summarizer.summarize({
    title: "테스트 제목",
    url: "https://example.com/article",
    bodyText: "테스트 본문",
  });

  assert.equal(calls, 2);
  assert.ok(summary.charCount <= 650);
  assert.equal(summary.briefing.highlights.length, 5);
});

test("GroqSummarizer formats structured news briefing output", async () => {
  const fetchStub: typeof fetch = async () => {
    const content = briefingContent();

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

  const summarizer = new GroqSummarizer("test-key", ["test-model"], 650, fetchStub);
  const summary = await summarizer.summarize({
    title: "테스트 기사 제목",
    url: "https://example.com/article",
    bodyText: "본문 텍스트",
  });

  assert.match(summary.summaryKo, /한눈에 보기/u);
  assert.match(summary.summaryKo, /왜 중요할까/u);
  assert.equal(summary.briefing.summary.length, 3);
  assert.equal(summary.briefing.highlights.length, 5);
  assert.equal(summary.briefing.importance.length, 3);
  assert.ok(summary.charCount <= 650);
});

test("GroqSummarizer falls back to the next model after rate limits", async () => {
  const requestedModels: string[] = [];
  const fetchStub: typeof fetch = async (_input, init) => {
    const body = JSON.parse(String(init?.body)) as { model: string };
    requestedModels.push(body.model);

    if (body.model === "openai/gpt-oss-120b") {
      return new Response("rate limit", {
        status: 429,
        headers: {
          "retry-after": "0",
        },
      });
    }

    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              content: briefingContent({
                lead: "백업 모델이 동일 기사 핵심 내용을 안정적으로 요약했습니다.",
              }),
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

  const summarizer = new GroqSummarizer(
    "test-key",
    ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"],
    800,
    fetchStub,
  );
  const summary = await summarizer.summarize({
    title: "테스트 제목",
    url: "https://example.com/article",
    bodyText: "테스트 본문",
  });

  assert.match(summary.summaryKo, /백업 모델/u);
  assert.deepEqual(requestedModels, [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
  ]);
});

test("DiscordNotifier renders Korean briefing embed fields", async () => {
  let payload: {
    embeds?: Array<{
      title?: string;
      description?: string;
      fields?: Array<{ name?: string; value?: string }>;
    }>;
  } | undefined;

  const notifier = new DiscordNotifier("https://discord.com/api/webhooks/test", async (_input, init) => {
    payload = JSON.parse(String(init?.body));
    return new Response("", { status: 200 });
  });

  await notifier.send(
    {
      sourceId: "threads-news",
      sourceName: "Threads",
      title: "무신사 AI 네이티브 워크플로우",
      url: "https://www.threads.com/@choi.openai/post/example/",
      publishedAt: "2026-04-30T13:24:00.000Z",
      category: "Posts",
      bodyText: "본문",
    },
    {
      summaryKo: "요약",
      charCount: 2,
      briefing: {
        lead: "오픈AI와 무신사가 AI 워크플로우 사례를 공유했습니다.",
        summary: [
          "Codex 도입 후 개발 방식이 설계와 검토 중심으로 바뀌었습니다.",
          "AI 활용 역량은 채용과 업무 방식의 핵심 기준으로 제시됐습니다.",
          "무신사는 패션 커머스에서 AI가 고객 접점과 운영 방식을 바꿀 수 있다고 설명했습니다.",
        ],
        highlights: [
          "오픈AI, 무신사 행사 참여",
          "Codex 기반 개발 워크플로우 소개",
          "AI 활용 능력 평가 강조",
          "패션 커머스 AI 전환 언급",
          "개발자의 역할 변화 사례 제시",
        ],
        importance: [
          "AI가 고객 인터페이스가 되면 커머스 경쟁 방식이 바뀝니다.",
          "특화 AI 역량은 패션 플랫폼의 차별화 요소가 됩니다.",
          "개발 조직은 코드 작성보다 설계와 검토 역량을 더 크게 요구받게 됩니다.",
        ],
      },
    },
  );

  const embed = payload?.embeds?.[0];
  assert.equal(embed?.title, "Threads 뉴스 브리핑");
  assert.match(embed?.description ?? "", /오픈AI와 무신사/u);
  assert.deepEqual(
    embed?.fields?.map((field) => field.name),
    ["한눈에 보기", "왜 중요할까", "출처", "발행 시각"],
  );
  assert.match(embed?.fields?.[0]?.value ?? "", /• 오픈AI/u);
  assert.equal(embed?.fields?.[2]?.value, "Threads");
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

  const summarizer = new GroqSummarizer("test-key", ["test-model"], 400, async () => {
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
