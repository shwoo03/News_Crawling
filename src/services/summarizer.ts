import type { FetchLike, SummaryResult } from "../types.ts";
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
    private readonly model: string,
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
      const normalized = normalizeSummary(summary);
      const readable = formatReadableSummary(normalized);
      if (!readable) {
        lastFailure = "Groq returned an empty summary.";
        continue;
      }

      if (readable.length <= this.maxCharacters) {
        return {
          summaryKo: readable,
          charCount: readable.length,
        };
      }

      lastFailure = `Groq returned ${readable.length} characters, exceeding the ${this.maxCharacters} character limit.`;
    }

    throw new Error(lastFailure);
  }

  private async requestSummary(userPrompt: string): Promise<string> {
    return this.requestSummaryWithRetry(userPrompt, 0);
  }

  private async requestSummaryWithRetry(userPrompt: string, attempt: number): Promise<string> {
    const response = await this.fetchImpl("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You summarize only the provided article body. Output must be in Korean, factual, concise, easy to read, and must not include outside knowledge or speculation.",
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
        return this.requestSummaryWithRetry(userPrompt, attempt + 1);
      }

      const errorText = await response.text();
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
    hardLimitInstruction,
    "Prefer short Korean sentences.",
    "Do not add guesses or background not explicitly stated in the source text.",
    "Do not use URLs, markdown links, tables, or hashtags.",
    `Title: ${input.title}`,
    `URL: ${input.url}`,
    "Body:",
    truncateForPrompt(input.bodyText, 12000),
  ].join("\n");
}

function normalizeSummary(value: string): string {
  return value
    .replace(/\r\n?/gu, "\n")
    .replace(/[ \t]+/gu, " ")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function formatReadableSummary(value: string): string {
  if (!value) {
    return "";
  }

  const normalized = value.replace(/\s*\n\s*/gu, "\n").trim();
  const lines = normalized.split(/\n+/u).filter(Boolean);
  const formattedSegments: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    const sentenceSplit = trimmed
      .split(/(?<=[.!?。！？])\s+/u)
      .map((sentence) => sentence.trim())
      .filter(Boolean);

    if (sentenceSplit.length <= 1) {
      formattedSegments.push(wrapByLineLength(trimmed, 110));
      continue;
    }

    for (const sentence of sentenceSplit) {
      formattedSegments.push(wrapByLineLength(sentence, 110));
    }
  }

  return formattedSegments.filter(Boolean).join("\n");
}

function wrapByLineLength(value: string, maxLineLength: number): string {
  if (value.length <= maxLineLength) {
    return value;
  }

  const words = value.split(" ");
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
