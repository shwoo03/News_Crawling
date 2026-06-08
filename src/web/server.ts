import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile } from "node:fs/promises";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Logger } from "../logger.ts";
import type { SourceAdapter } from "../types.ts";
import type { SqliteStateStore } from "../storage/sqlite.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const STATIC_ROOT = resolve(HERE, "static");

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".png": "image/png",
};

const DISCORD_WEBHOOK_PATTERN = /^https:\/\/discord(?:app)?\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+$/u;

export type DashboardServer = {
  start(): Promise<void>;
  close(): Promise<void>;
};

export function createDashboardServer(input: {
  store: SqliteStateStore;
  sources: SourceAdapter[];
  logger: Logger;
  port: number;
  host: string;
}): DashboardServer {
  const { store, sources, logger, port, host } = input;
  const sourceCatalog = sources.map((source) => ({
    id: source.id,
    name: source.name,
    rssUrl: source.rssUrl,
  }));

  const server = createServer(async (request, response) => {
    try {
      await route(request, response, { store, sourceCatalog, logger });
    } catch (error) {
      logger.error("Dashboard request crashed.", {
        method: request.method,
        url: request.url,
        error: error instanceof Error ? error.message : String(error),
      });
      sendJson(response, 500, { error: "internal_server_error" });
    }
  });

  return {
    start(): Promise<void> {
      return new Promise((resolveStart, reject) => {
        const onError = (error: Error) => reject(error);
        server.once("error", onError);
        server.listen(port, host, () => {
          server.off("error", onError);
          logger.info("Dashboard server listening.", { host, port });
          resolveStart();
        });
      });
    },
    close(): Promise<void> {
      return new Promise((resolveClose) => {
        server.close(() => resolveClose());
      });
    },
  };
}

type SourceCatalogEntry = { id: string; name: string; rssUrl: string };

type RouteContext = {
  store: SqliteStateStore;
  sourceCatalog: SourceCatalogEntry[];
  logger: Logger;
};

async function route(
  request: IncomingMessage,
  response: ServerResponse,
  context: RouteContext,
): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  const method = request.method ?? "GET";
  const path = url.pathname;

  if (path.startsWith("/api/")) {
    await handleApi(request, response, context, method, path);
    return;
  }

  await serveStatic(response, path);
}

async function handleApi(
  request: IncomingMessage,
  response: ServerResponse,
  context: RouteContext,
  method: string,
  path: string,
): Promise<void> {
  if (method === "GET" && path === "/api/state") {
    sendJson(response, 200, {
      sources: context.sourceCatalog,
      webhooks: context.store.listWebhooks().map(maskWebhook),
      routes: context.store.listRoutes(),
      settings: {
        hasGroqApiKey: Boolean(context.store.getSetting("groq_api_key")?.trim()),
      },
    });
    return;
  }

  if (method === "GET" && path === "/api/webhooks") {
    sendJson(response, 200, context.store.listWebhooks().map(maskWebhook));
    return;
  }

  if (method === "POST" && path === "/api/webhooks") {
    const body = await readJsonBody<{ label?: string; url?: string }>(request);
    const label = body.label?.trim();
    const url = body.url?.trim();
    if (!label) {
      sendJson(response, 400, { error: "label_required" });
      return;
    }
    if (!url || !DISCORD_WEBHOOK_PATTERN.test(url)) {
      sendJson(response, 400, { error: "invalid_discord_webhook_url" });
      return;
    }

    const created = context.store.createWebhook({ label, url });
    sendJson(response, 201, maskWebhook(created));
    return;
  }

  const webhookIdMatch = /^\/api\/webhooks\/(\d+)$/u.exec(path);
  if (webhookIdMatch) {
    const id = Number(webhookIdMatch[1]);

    if (method === "PATCH" || method === "PUT") {
      const body = await readJsonBody<{ label?: string; url?: string }>(request);
      const patch: { label?: string; url?: string } = {};
      if (body.label !== undefined) {
        const label = body.label.trim();
        if (!label) {
          sendJson(response, 400, { error: "label_required" });
          return;
        }
        patch.label = label;
      }
      if (body.url !== undefined) {
        const url = body.url.trim();
        if (!url || !DISCORD_WEBHOOK_PATTERN.test(url)) {
          sendJson(response, 400, { error: "invalid_discord_webhook_url" });
          return;
        }
        patch.url = url;
      }

      const updated = context.store.updateWebhook(id, patch);
      if (!updated) {
        sendJson(response, 404, { error: "webhook_not_found" });
        return;
      }
      sendJson(response, 200, maskWebhook(updated));
      return;
    }

    if (method === "DELETE") {
      const removed = context.store.deleteWebhook(id);
      sendJson(response, removed ? 200 : 404, { removed });
      return;
    }
  }

  if (method === "GET" && path === "/api/routes") {
    sendJson(response, 200, context.store.listRoutes());
    return;
  }

  if (method === "POST" && path === "/api/routes") {
    const body = await readJsonBody<{
      sourceId?: string;
      webhookId?: number;
      pollIntervalMinutes?: number;
      enabled?: boolean;
    }>(request);

    const validation = validateRouteInput(body, context);
    if (!validation.ok) {
      sendJson(response, 400, { error: validation.error });
      return;
    }

    const created = context.store.createRoute({
      sourceId: validation.value.sourceId,
      webhookId: validation.value.webhookId,
      pollIntervalMinutes: validation.value.pollIntervalMinutes,
      enabled: validation.value.enabled,
    });
    sendJson(response, 201, created);
    return;
  }

  const routeIdMatch = /^\/api\/routes\/(\d+)$/u.exec(path);
  if (routeIdMatch) {
    const id = Number(routeIdMatch[1]);

    if (method === "PATCH" || method === "PUT") {
      const body = await readJsonBody<{
        sourceId?: string;
        webhookId?: number;
        pollIntervalMinutes?: number;
        enabled?: boolean;
      }>(request);

      const patch: {
        sourceId?: string;
        webhookId?: number;
        pollIntervalMinutes?: number;
        enabled?: boolean;
      } = {};

      if (body.sourceId !== undefined) {
        if (!context.sourceCatalog.some((source) => source.id === body.sourceId)) {
          sendJson(response, 400, { error: "unknown_source" });
          return;
        }
        patch.sourceId = body.sourceId;
      }
      if (body.webhookId !== undefined) {
        if (!context.store.getWebhook(body.webhookId)) {
          sendJson(response, 400, { error: "unknown_webhook" });
          return;
        }
        patch.webhookId = body.webhookId;
      }
      if (body.pollIntervalMinutes !== undefined) {
        const minutes = Number(body.pollIntervalMinutes);
        if (!Number.isInteger(minutes) || minutes < 1) {
          sendJson(response, 400, { error: "invalid_interval" });
          return;
        }
        patch.pollIntervalMinutes = minutes;
      }
      if (body.enabled !== undefined) {
        patch.enabled = Boolean(body.enabled);
      }

      const updated = context.store.updateRoute(id, patch);
      if (!updated) {
        sendJson(response, 404, { error: "route_not_found" });
        return;
      }
      sendJson(response, 200, updated);
      return;
    }

    if (method === "DELETE") {
      const removed = context.store.deleteRoute(id);
      sendJson(response, removed ? 200 : 404, { removed });
      return;
    }
  }

  if (method === "GET" && path === "/api/settings/groq") {
    const stored = context.store.getSetting("groq_api_key")?.trim() ?? "";
    sendJson(response, 200, {
      hasGroqApiKey: stored.length > 0,
      preview: stored ? maskSecret(stored) : null,
    });
    return;
  }

  if ((method === "PUT" || method === "POST") && path === "/api/settings/groq") {
    const body = await readJsonBody<{ apiKey?: string }>(request);
    const apiKey = body.apiKey?.trim();
    if (!apiKey) {
      sendJson(response, 400, { error: "api_key_required" });
      return;
    }
    context.store.setSetting("groq_api_key", apiKey);
    sendJson(response, 200, { ok: true, preview: maskSecret(apiKey) });
    return;
  }

  if (method === "DELETE" && path === "/api/settings/groq") {
    context.store.clearSetting("groq_api_key");
    sendJson(response, 200, { ok: true });
    return;
  }

  if (method === "POST" && path === "/api/reset") {
    context.store.clearWebhooks();
    context.store.clearSetting("groq_api_key");
    sendJson(response, 200, { ok: true });
    return;
  }

  sendJson(response, 404, { error: "not_found", method, path });
}

type RouteValidationResult =
  | {
      ok: true;
      value: {
        sourceId: string;
        webhookId: number;
        pollIntervalMinutes: number;
        enabled: boolean;
      };
    }
  | { ok: false; error: string };

function validateRouteInput(
  body: {
    sourceId?: string;
    webhookId?: number;
    pollIntervalMinutes?: number;
    enabled?: boolean;
  },
  context: RouteContext,
): RouteValidationResult {
  if (!body.sourceId || !context.sourceCatalog.some((source) => source.id === body.sourceId)) {
    return { ok: false, error: "unknown_source" };
  }
  if (typeof body.webhookId !== "number" || !context.store.getWebhook(body.webhookId)) {
    return { ok: false, error: "unknown_webhook" };
  }
  const minutes = Number(body.pollIntervalMinutes);
  if (!Number.isInteger(minutes) || minutes < 1) {
    return { ok: false, error: "invalid_interval" };
  }

  return {
    ok: true,
    value: {
      sourceId: body.sourceId,
      webhookId: body.webhookId,
      pollIntervalMinutes: minutes,
      enabled: body.enabled === undefined ? true : Boolean(body.enabled),
    },
  };
}

function maskWebhook(webhook: { id: number; label: string; url: string; createdAt: string }): {
  id: number;
  label: string;
  url: string;
  preview: string;
  createdAt: string;
} {
  return {
    id: webhook.id,
    label: webhook.label,
    url: webhook.url,
    preview: previewWebhook(webhook.url),
    createdAt: webhook.createdAt,
  };
}

function previewWebhook(value: string): string {
  try {
    const url = new URL(value);
    const parts = url.pathname.split("/");
    const id = parts[3] ?? "";
    const token = parts[4] ?? "";
    const tail = token ? `${token.slice(0, 6)}…${token.slice(-4)}` : "";
    return `${url.hostname}/${id}/${tail}`;
  } catch {
    return "invalid-url";
  }
}

function maskSecret(value: string): string {
  if (value.length <= 8) {
    return "•".repeat(value.length);
  }
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

async function readJsonBody<T>(request: IncomingMessage): Promise<T> {
  return new Promise<T>((resolveBody, reject) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      if (!raw) {
        resolveBody({} as T);
        return;
      }
      try {
        resolveBody(JSON.parse(raw) as T);
      } catch {
        reject(new Error("invalid_json_body"));
      }
    });
    request.on("error", reject);
  });
}

function sendJson(response: ServerResponse, status: number, payload: unknown): void {
  response.statusCode = status;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.setHeader("cache-control", "no-store");
  response.end(JSON.stringify(payload));
}

async function serveStatic(response: ServerResponse, path: string): Promise<void> {
  const safePath = normalize(path === "/" ? "/index.html" : path).replace(/^\/+/u, "");
  const target = join(STATIC_ROOT, safePath);
  if (!target.startsWith(STATIC_ROOT)) {
    sendJson(response, 403, { error: "forbidden" });
    return;
  }

  try {
    const data = await readFile(target);
    const mime = MIME_TYPES[extname(target)] ?? "application/octet-stream";
    response.statusCode = 200;
    response.setHeader("content-type", mime);
    response.setHeader("cache-control", "no-cache");
    response.end(data);
  } catch (error) {
    if (isNodeError(error) && error.code === "ENOENT") {
      sendJson(response, 404, { error: "not_found", path });
      return;
    }
    throw error;
  }
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
