import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { join } from "node:path";
import { parseAnthropicListItems, extractArticleBody } from "../src/sources/anthropic-news.ts";

test("parseAnthropicListItems reads list items and normalizes URLs", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "anthropic-news-list.html"), "utf8");
  const items = parseAnthropicListItems(fixture);

  assert.equal(items.length, 10);
  assert.equal(items[0]?.id, "https://www.anthropic.com/news/australia-MOU/");
  assert.equal(items[0]?.title, "Australian government and Anthropic sign MOU for AI safety and research");
  assert.equal(items[0]?.category, "Announcements");
  assert.equal(items[0]?.publishedAt, new Date("Mar 31, 2026").toISOString());
  assert.equal(items[9]?.id, "https://www.anthropic.com/news/responsible-scaling-policy-v3/");

  for (const item of items) {
    assert.equal(item.id.endsWith("/"), true);
  }
});

test("extractArticleBody keeps article text and removes share noise", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures", "anthropic-article.html"), "utf8");
  const body = extractArticleBody(fixture, {
    title: "Australian government and Anthropic sign MOU for AI safety and research",
    publishedAt: "2026-03-31T00:00:00.000Z",
    category: "Announcements",
  });

  assert.match(body, /Today, Anthropic signed a Memorandum/);
  assert.match(body, /This is the paragraph we want to summarize/);
  assert.doesNotMatch(body, /Share on Twitter/);
  assert.doesNotMatch(body, /Share on LinkedIn/);
});

test("extractArticleBody throws on empty container", () => {
  const fixture = readFileSync(
    join(import.meta.dirname, "fixtures", "anthropic-article-empty-body.html"),
    "utf8",
  );
  assert.throws(
    () =>
      extractArticleBody(fixture, {
        title: "Empty body example",
        publishedAt: "2026-03-31T00:00:00.000Z",
        category: "Test",
      }),
    { message: "Article body is empty after parsing." },
  );
});
