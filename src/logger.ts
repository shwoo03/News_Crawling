import type { LogFormat, LogLevel } from "./types.ts";

const levels: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

export class Logger {
  constructor(
    private readonly minimumLevel: LogLevel,
    private readonly format: LogFormat = "pretty",
  ) {}

  debug(message: string, context?: Record<string, unknown>): void {
    this.write("debug", message, context);
  }

  info(message: string, context?: Record<string, unknown>): void {
    this.write("info", message, context);
  }

  warn(message: string, context?: Record<string, unknown>): void {
    this.write("warn", message, context);
  }

  error(message: string, context?: Record<string, unknown>): void {
    this.write("error", message, context);
  }

  private write(level: LogLevel, message: string, context?: Record<string, unknown>): void {
    if (levels[level] < levels[this.minimumLevel]) {
      return;
    }

    if (this.format === "pretty") {
      const contextText = formatContext(context);
      const time = new Date().toLocaleTimeString("ko-KR", { hour12: false });
      const prefix = `[${time}] [${level.toUpperCase()}]`;
      const line = `${prefix} ${message}${contextText}`;
      if (level === "error" || level === "warn") {
        console.error(line);
        return;
      }

      console.log(line);
      return;
    }

    const payload = {
      level,
      time: new Date().toISOString(),
      message,
      ...(context ?? {}),
    };

    const line = JSON.stringify(payload);
    if (level === "error" || level === "warn") {
      console.error(line);
      return;
    }

    console.log(line);
  }
}

function formatContext(context?: Record<string, unknown>): string {
  if (!context || Object.keys(context).length === 0) {
    return "";
  }

  const pairs = Object.entries(context).map(
    ([key, value]) => `${key}=${formatContextValue(value)}`,
  );

  return ` | ${pairs.join(" ")}`;
}

function formatContextValue(value: unknown): string {
  if (value == null) {
    return "null";
  }

  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value)) {
    if (value.length <= 3) {
      return value.map((item) => formatContextValue(item)).join(", ");
    }

    return `[${value.slice(0, 3).map((item) => formatContextValue(item)).join(", ")}, ... +${value.length - 3}]`;
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}
