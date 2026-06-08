import { resolve } from "node:path";
import type { LogFormat, LogLevel } from "./types.ts";

export type AppConfig = {
  groqApiKey?: string;
  groqModels: string[];
  summaryMaxCharacters: number;
  topTestArticleCount: number;
  topTestReferenceUrl?: string;
  logLevel: LogLevel;
  logFormat: LogFormat;
  sqlitePath: string;
  dashboardPort: number;
  dashboardHost: string;
};

export function getConfig(): AppConfig {
  const groqApiKey = process.env.GROQ_API_KEY?.trim() || undefined;
  const groqModels = resolveGroqModels();
  const summaryMaxCharacters = parsePositiveInteger(process.env.SUMMARY_MAX_CHARACTERS, 1800);
  const topTestArticleCount = parsePositiveInteger(process.env.TOP_TEST_ARTICLE_COUNT, 2);
  const topTestReferenceUrl = process.env.TOP_TEST_REFERENCE_URL?.trim() || undefined;
  const logLevel = parseLogLevel(process.env.LOG_LEVEL);
  const logFormat = parseLogFormat(process.env.LOG_FORMAT);
  const sqlitePath = resolve(process.env.SQLITE_PATH?.trim() || "./data/news-crawling.sqlite");
  const dashboardPort = parsePositiveInteger(process.env.DASHBOARD_PORT, 3000);
  const dashboardHost = process.env.DASHBOARD_HOST?.trim() || "0.0.0.0";

  return {
    groqApiKey,
    groqModels,
    summaryMaxCharacters,
    topTestArticleCount,
    topTestReferenceUrl,
    logLevel,
    logFormat,
    sqlitePath,
    dashboardPort,
    dashboardHost,
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
