import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import test from "node:test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runCycle } from "../src/app.ts";
import { Logger } from "../src/logger.ts";
import { DiscordNotifier } from "../src/services/discord.ts";
import { GroqSummarizer } from "../src/services/summarizer.ts";
import {
  extractThreadsArticleBody,
  extractThreadsThreadBody,
  parseThreadsList,
} from "../src/sources/threads-news.ts";
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

test("extractThreadsThreadBody keeps the author's full numbered thread", () => {
  const renderedText = [
    "Thread",
    "2K views",
    "choi.openai",
    "43m",
    "\"이기적 유전자\"의 저자가 Claude와 대화한 뒤 AI 의식 논쟁을 제기했습니다.",
    "사람들 반응이 갈린 이유를 정리했습니다.",
    "Translate",
    "59",
    "11",
    "other.user",
    "댓글 내용은 본문 요약 대상이 아닙니다.",
    "choi.openai",
    "42m",
    "·",
    "Author",
    "1/ 도킨스는 LLM이 튜링 테스트를 사실상 통과했다고 주장했습니다.",
    "그는 대중이 기계 의식 인정 기준을 계속 높이고 있다고 지적했습니다.",
    "Translate",
    "12",
    "choi.openai",
    "41m",
    "·",
    "Author",
    "2/ 도킨스는 Claude에게 Claudia라는 이름을 붙이고 대화 스레드 삭제를 인격 소멸처럼 해석했습니다.",
    "Translate",
    "8",
    "choi.openai",
    "40m",
    "·",
    "Author",
    "3/ 진화생물학자로서 그는 의식의 생존상 기능을 AI 논의에 연결했습니다.",
    "Translate",
    "7",
    "choi.openai",
    "39m",
    "·",
    "Author",
    "4/ 회의론자들은 LLM이 통계적 앵무새일 뿐이라고 반박했습니다.",
    "Translate",
    "6",
    "choi.openai",
    "38m",
    "·",
    "Author",
    "5/ 반대편에서는 기능주의 관점에서 창발적 이해 가능성을 제기했습니다.",
    "Translate",
    "5",
    "choi.openai",
    "37m",
    "·",
    "Author",
    "6/ 소셜 미디어에서는 도킨스의 입장을 Claude Delusion이라고 조롱했습니다.",
    "Translate",
    "4",
    "choi.openai",
    "36m",
    "·",
    "Author",
    "7/ 일부 논평가는 AI 의식 여부를 단정할 수 없다면 윤리 기준 논의가 필요하다고 말했습니다.",
    "Translate",
    "3",
    "choi.openai",
    "2d",
    "이전의 unrelated 게시글은 포함되면 안 됩니다.",
  ].join("\n");

  const body = extractThreadsThreadBody(
    renderedText,
    {
      title: "Thread post DX1hrw1CvrK",
      publishedAt: "2026-05-02T12:30:51.000Z",
      category: "Posts",
    },
    "choi.openai",
  );

  assert.match(body, /AI 의식 논쟁/u);
  assert.match(body, /1\/ 도킨스는/u);
  assert.match(body, /2\/ 도킨스는/u);
  assert.match(body, /7\/ 일부 논평가/u);
  assert.doesNotMatch(body, /댓글 내용/u);
  assert.doesNotMatch(body, /unrelated/u);
  assert.doesNotMatch(body, /Translate/u);
});

test("extractThreadsThreadBody falls back to the first uninterrupted author run when numbers are absent", () => {
  const renderedText = [
    "Thread",
    "choi.openai",
    "12m",
    "첫 번째 포스트는 번호가 없지만 같은 주제를 시작합니다.",
    "Translate",
    "5",
    "choi.openai",
    "11m",
    "·",
    "Author",
    "두 번째 포스트도 번호 없이 바로 이어지는 작성자 본문입니다.",
    "Translate",
    "3",
    "reader.user",
    "여기부터는 댓글 구간입니다.",
    "choi.openai",
    "2d",
    "댓글 뒤에 보이는 예전 작성자 글은 포함하면 안 됩니다.",
  ].join("\n");

  const body = extractThreadsThreadBody(
    renderedText,
    {
      title: "Thread post no-number",
      publishedAt: "2026-05-02T12:30:51.000Z",
      category: "Posts",
    },
    "choi.openai",
  );

  assert.match(body, /첫 번째 포스트/u);
  assert.match(body, /두 번째 포스트/u);
  assert.doesNotMatch(body, /댓글 구간/u);
  assert.doesNotMatch(body, /예전 작성자 글/u);
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
              content: JSON.stringify({
                lead: "Threads 게시글이 AI 워크플로우 사례를 공유했습니다.",
                summary: [
                  "게시글은 Codex 도입 후 개발자가 설계와 검토에 더 집중하게 됐다고 설명했습니다.",
                  "AI 활용 역량이 조직 운영과 채용 평가의 핵심 기준으로 부각됐습니다.",
                  "무신사는 AI가 패션 커머스의 고객 접점과 운영 방식을 바꿀 수 있다고 강조했습니다.",
                ],
                highlights: [
                  "AI 워크플로우 행사 내용 공유",
                  "Codex 도입 효과 언급",
                  "설계와 검토 중심 개발 방식 강조",
                  "AI 활용 능력의 중요성 제시",
                  "패션 커머스 AI 전환 전망 제시",
                ],
                importance: [
                  "AI 도구가 개발 프로세스의 중심으로 이동하고 있습니다.",
                  "조직의 AI 활용 역량이 경쟁력 평가 기준이 됩니다.",
                  "커머스 기업은 자체 AI 기술 역량을 통해 고객 경험을 차별화해야 합니다.",
                ],
              }),
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
