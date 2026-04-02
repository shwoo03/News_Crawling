import { resolve } from "node:path";
import type { LogFormat, LogLevel } from "./types.ts";

export type AppConfig = {
  groqApiKey: string;
  groqModels: string[];
  discordWebhookUrl?: string;
  summaryMaxCharacters: number;
  topTestArticleCount: number;
  topTestReferenceUrl?: string;
  pollIntervalMinutes: number;
  logLevel: LogLevel;
  logFormat: LogFormat;
  sqlitePath: string;
};

export function getConfig(): AppConfig {
  const groqApiKey = process.env.GROQ_API_KEY?.trim();
  if (!groqApiKey) {
    throw new Error("GROQ_API_KEY is required.");
  }

  const groqModels = resolveGroqModels();
  const summaryMaxCharacters = parsePositiveInteger(process.env.SUMMARY_MAX_CHARACTERS, 800);
  const topTestArticleCount = parsePositiveInteger(process.env.TOP_TEST_ARTICLE_COUNT, 2);
  const topTestReferenceUrl = process.env.TOP_TEST_REFERENCE_URL?.trim() || undefined;
  const pollIntervalMinutes = parsePositiveInteger(process.env.POLL_INTERVAL_MINUTES, 10);
  const logLevel = parseLogLevel(process.env.LOG_LEVEL);
  const logFormat = parseLogFormat(process.env.LOG_FORMAT);
  const sqlitePath = resolve(process.env.SQLITE_PATH?.trim() || "./data/news-crawling.sqlite");
  const discordWebhookUrl = resolveWebhookUrl();

  return {
    groqApiKey,
    groqModels,
    discordWebhookUrl,
    summaryMaxCharacters,
    topTestArticleCount,
    topTestReferenceUrl,
    pollIntervalMinutes,
    logLevel,
    logFormat,
    sqlitePath,
  };
}

function resolveGroqModels(): string[] {
  const primary = process.env.GROQ_MODEL?.trim() || "openai/gpt-oss-120b";
  const fallbackRaw = process.env.GROQ_MODEL_FALLBACKS?.trim() || "";
  const fallbacks = fallbackRaw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  return [...new Set([primary, ...fallbacks])];
}

function resolveWebhookUrl(): string | undefined {
  const directUrl = process.env.DISCORD_WEBHOOK_URL?.trim();
  if (directUrl) {
    return directUrl;
  }

  const webhookId = process.env.DISCORD_WEBHOOK_ID?.trim();
  const webhookToken = process.env.DISCORD_WEBHOOK_TOKEN?.trim();

  if (!webhookId || !webhookToken) {
    return undefined;
  }

  return `https://discord.com/api/webhooks/${webhookId}/${webhookToken}`;
}

function parsePositiveInteger(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Invalid positive integer: ${value}`);
  }

  return parsed;
}

function parseLogLevel(value: string | undefined): LogLevel {
  switch (value) {
    case "debug":
    case "info":
    case "warn":
    case "error":
      return value;
    default:
      return "info";
  }
}

function parseLogFormat(value: string | undefined): LogFormat {
  switch (value) {
    case "pretty":
    case "json":
      return value;
    default:
      return "pretty";
  }
}
