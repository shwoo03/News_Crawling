import type { FetchLike, SummaryBriefing, SummaryResult } from "../types.ts";
import { truncateForPrompt } from "../utils/text.ts";
import { setTimeout as delay } from "node:timers/promises";

type GroqResponse = {
  choices?: Array<{
    message?: {
      content?: string | Array<{ type?: string; text?: string }>;
    };
  }>;
};

export class GroqSummarizer {
  constructor(
    private readonly apiKey: string,
    private readonly models: string[],
    private readonly maxCharacters: number,
    private readonly fetchImpl: FetchLike = fetch,
  ) {}

  async summarize(input: { title: string; bodyText: string; url: string }): Promise<SummaryResult> {
    const compactTarget = Math.max(Math.floor(this.maxCharacters * 0.8), 200);
    const attempts = [
      buildUserPrompt(input, false, this.maxCharacters),
      buildUserPrompt(input, true, this.maxCharacters),
      buildUserPrompt(input, true, this.maxCharacters, compactTarget),
    ];

    let lastFailure = "Unknown summarization error.";
    for (const prompt of attempts) {
      const summary = await this.requestSummary(prompt);
      let briefing: SummaryBriefing;
      try {
        briefing = parseBriefingSummary(summary);
      } catch (error) {
        lastFailure = `Groq returned invalid briefing JSON: ${error instanceof Error ? error.message : String(error)}`;
        continue;
      }

      const readable = formatBriefingSummary(briefing);
      if (!readable) {
        lastFailure = "Groq returned an empty summary.";
        continue;
      }

      if (readable.length <= this.maxCharacters) {
        return {
          summaryKo: readable,
          charCount: readable.length,
          briefing,
        };
      }

      lastFailure = `Groq returned ${readable.length} characters, exceeding the ${this.maxCharacters} character limit.`;
    }

    throw new Error(lastFailure);
  }

  private async requestSummary(userPrompt: string): Promise<string> {
    let lastRateLimitError: GroqRateLimitError | undefined;

    for (const model of this.models) {
      try {
        return await this.requestSummaryWithRetry(userPrompt, model, 0);
      } catch (error) {
        if (error instanceof GroqRateLimitError) {
          lastRateLimitError = error;
          continue;
        }

        throw error;
      }
    }

    throw lastRateLimitError ?? new Error("Groq request failed before any model could respond.");
  }

  private async requestSummaryWithRetry(userPrompt: string, model: string, attempt: number): Promise<string> {
    const response = await this.fetchImpl("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You summarize only the provided article body. Output must be Korean JSON only, factual, concise, easy to read, and must not include outside knowledge or speculation.",
          },
          {
            role: "user",
            content: userPrompt,
          },
        ],
      }),
    });

    if (!response.ok) {
      if (response.status === 429 && attempt < 2) {
        const retryAfter = Number.parseInt(response.headers.get("retry-after") ?? "", 10);
        const retryMs =
          Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : (attempt + 1) * 5000;
        await delay(retryMs);
        return this.requestSummaryWithRetry(userPrompt, model, attempt + 1);
      }

      const errorText = await response.text();
      if (response.status === 429) {
        throw new GroqRateLimitError(model, errorText || "Rate limit exceeded.");
      }

      throw new Error(`Groq request failed with status ${response.status}: ${errorText}`);
    }

    const payload = (await response.json()) as GroqResponse;
    const content = payload.choices?.[0]?.message?.content;

    if (typeof content === "string") {
      return content;
    }

    if (Array.isArray(content)) {
      return content.map((part) => part.text ?? "").join("").trim();
    }

    throw new Error("Groq response did not include summary content.");
  }
}

class GroqRateLimitError extends Error {
  constructor(model: string, detail: string) {
    super(`Groq rate limit hit for model ${model}: ${detail}`);
    this.name = "GroqRateLimitError";
  }
}

function buildUserPrompt(
  input: { title: string; bodyText: string; url: string },
  strictRetry: boolean,
  maxCharacters: number,
  targetCharacters = maxCharacters,
): string {
  const hardLimitInstruction = strictRetry
    ? `Output should be under ${targetCharacters} characters.`
    : `Output should be under ${maxCharacters} characters.`;

  return [
    "Use only the article body below. Summarize only facts present in the provided content.",
    `The final rendered briefing should be under ${targetCharacters} Korean characters. ${hardLimitInstruction}`,
    "Return valid JSON only. Do not wrap it in markdown.",
    "Use this exact shape:",
    "{\"lead\":\"원문의 핵심 분위기를 살린 도입 1문장\",\"summary\":[\"핵심 요약 1\",\"핵심 요약 2\",\"핵심 요약 3\"],\"highlights\":[\"한눈에 보기 1\",\"한눈에 보기 2\",\"한눈에 보기 3\",\"한눈에 보기 4\",\"한눈에 보기 5\"],\"importance\":[\"왜 중요한지 1\",\"왜 중요한지 2\",\"왜 중요한지 3\"]}",
    "Field rules:",
    "- lead: 1 sentence, engaging but factual.",
    "- summary: exactly 3 Korean sentences with concrete details from the source.",
    "- highlights: exactly 5 concise Korean bullet items.",
    "- importance: exactly 3 Korean bullet items explaining practical implications from the source.",
    "Do not add guesses or background not explicitly stated in the source text.",
    "Do not use URLs, markdown links, tables, or hashtags.",
    `Title: ${input.title}`,
    `URL: ${input.url}`,
    "Body:",
    truncateForPrompt(input.bodyText, 12000),
  ].join("\n");
}

function parseBriefingSummary(value: string): SummaryBriefing {
  const parsed = parseJsonObject(value);
  const briefing = {
    lead: readString(parsed, "lead"),
    summary: readStringArray(parsed, "summary", 3),
    highlights: readStringArray(parsed, "highlights", 5),
    importance: readStringArray(parsed, "importance", 3),
  };

  if (!briefing.lead) {
    throw new Error("lead is required.");
  }

  return briefing;
}

function parseJsonObject(value: string): Record<string, unknown> {
  const normalized = normalizeText(value).replace(/^```(?:json)?\s*/iu, "").replace(/\s*```$/u, "");

  try {
    const parsed = JSON.parse(normalized);
    if (isRecord(parsed)) {
      return parsed;
    }
  } catch {
    // Try extracting the first JSON object from responses that include small wrappers.
  }

  const start = normalized.indexOf("{");
  const end = normalized.lastIndexOf("}");
  if (start >= 0 && end > start) {
    const parsed = JSON.parse(normalized.slice(start, end + 1));
    if (isRecord(parsed)) {
      return parsed;
    }
  }

  throw new Error("response is not a JSON object.");
}

function readString(input: Record<string, unknown>, key: string): string {
  const value = input[key];
  if (typeof value !== "string") {
    throw new Error(`${key} must be a string.`);
  }

  const normalized = cleanBriefingLine(value);
  if (!normalized) {
    throw new Error(`${key} must not be empty.`);
  }

  return normalized;
}

function readStringArray(input: Record<string, unknown>, key: string, count: number): string[] {
  const value = input[key];
  if (!Array.isArray(value)) {
    throw new Error(`${key} must be an array.`);
  }

  const normalized = value
    .filter((item): item is string => typeof item === "string")
    .map(cleanBriefingLine)
    .filter(Boolean);

  if (normalized.length < count) {
    throw new Error(`${key} must include at least ${count} text items.`);
  }

  return normalized.slice(0, count);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function cleanBriefingLine(value: string): string {
  return normalizeText(value)
    .replace(/^[•\-\d.)\s]+/u, "")
    .trim();
}

function normalizeText(value: string): string {
  return value
    .replace(/\r\n?/gu, "\n")
    .replace(/[ \t]+/gu, " ")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function formatBriefingSummary(briefing: SummaryBriefing): string {
  const parts = [
    briefing.lead,
    "",
    ...briefing.summary.map((item) => wrapByLineLength(item, 110)),
    "",
    "한눈에 보기",
    ...briefing.highlights.map((item) => `• ${wrapByLineLength(item, 100)}`),
    "",
    "왜 중요할까",
    ...briefing.importance.map((item) => `• ${wrapByLineLength(item, 100)}`),
  ];

  return parts.join("\n").trim();
}

function wrapByLineLength(value: string, maxLineLength: number): string {
  if (value.length <= maxLineLength) {
    return value;
  }

  const words = value.split(" ");
  if (words.length <= 1) {
    return value;
  }

  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    if (!current) {
      current = word;
      continue;
    }

    const next = `${current} ${word}`;
    if (next.length > maxLineLength) {
      lines.push(current);
      current = word;
      continue;
    }

    current = next;
  }

  if (current) {
    lines.push(current);
  }

  return lines.join("\n");
}
