import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

export type WebhookRecord = {
  id: number;
  label: string;
  url: string;
  createdAt: string;
};

export type RouteRecord = {
  id: number;
  sourceId: string;
  webhookId: number;
  pollIntervalMinutes: number;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  lastRunAt: string | null;
};

export class SqliteStateStore {
  private readonly db: DatabaseSync;

  constructor(databasePath: string) {
    mkdirSync(dirname(databasePath), { recursive: true });
    this.db = new DatabaseSync(databasePath);
    this.initialize();
  }

  ensureSource(source: { id: string; name: string; rssUrl: string }): void {
    this.db
      .prepare(
        `
          INSERT INTO sources (id, name, rss_url, last_checked_at)
          VALUES (?, ?, ?, ?)
          ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            rss_url = excluded.rss_url
        `,
      )
      .run(source.id, source.name, source.rssUrl, new Date().toISOString());
  }

  hasSeen(sourceId: string, url: string): boolean {
    const row = this.db
      .prepare("SELECT 1 AS found FROM articles WHERE source_id = ? AND url = ? LIMIT 1")
      .get(sourceId, url) as { found?: number } | undefined;

    return row?.found === 1;
  }

  countArticlesForSource(sourceId: string): number {
    const row = this.db
      .prepare("SELECT COUNT(*) AS total FROM articles WHERE source_id = ?")
      .get(sourceId) as { total: number };

    return row.total;
  }

  markSeen(input: {
    sourceId: string;
    title: string;
    url: string;
    publishedAt: string;
    category: string;
  }): number {
    this.db
      .prepare(
        `
          INSERT INTO articles (source_id, title, url, category, published_at, first_seen_at)
          VALUES (?, ?, ?, ?, ?, ?)
        `,
      )
      .run(
        input.sourceId,
        input.title,
        input.url,
        input.category,
        input.publishedAt,
        new Date().toISOString(),
      );

    const row = this.db
      .prepare("SELECT id FROM articles WHERE source_id = ? AND url = ? LIMIT 1")
      .get(input.sourceId, input.url) as { id: number };

    return row.id;
  }

  recordDelivery(input: {
    articleId: number;
    status: string;
    webhookTarget: string | null;
    errorMessage?: string;
  }): void {
    this.db
      .prepare(
        `
          INSERT INTO deliveries (article_id, status, webhook_target, delivered_at, error_message)
          VALUES (?, ?, ?, ?, ?)
        `,
      )
      .run(
        input.articleId,
        input.status,
        input.webhookTarget,
        new Date().toISOString(),
        input.errorMessage ?? null,
      );
  }

  listWebhooks(): WebhookRecord[] {
    const rows = this.db
      .prepare("SELECT id, label, url, created_at FROM webhooks ORDER BY id ASC")
      .all() as Array<{ id: number; label: string; url: string; created_at: string }>;

    return rows.map((row) => ({
      id: row.id,
      label: row.label,
      url: row.url,
      createdAt: row.created_at,
    }));
  }

  getWebhook(id: number): WebhookRecord | undefined {
    const row = this.db
      .prepare("SELECT id, label, url, created_at FROM webhooks WHERE id = ?")
      .get(id) as { id: number; label: string; url: string; created_at: string } | undefined;

    if (!row) {
      return undefined;
    }

    return { id: row.id, label: row.label, url: row.url, createdAt: row.created_at };
  }

  createWebhook(input: { label: string; url: string }): WebhookRecord {
    const createdAt = new Date().toISOString();
    const result = this.db
      .prepare("INSERT INTO webhooks (label, url, created_at) VALUES (?, ?, ?)")
      .run(input.label, input.url, createdAt);

    return {
      id: Number(result.lastInsertRowid),
      label: input.label,
      url: input.url,
      createdAt,
    };
  }

  updateWebhook(id: number, patch: { label?: string; url?: string }): WebhookRecord | undefined {
    const existing = this.getWebhook(id);
    if (!existing) {
      return undefined;
    }

    const nextLabel = patch.label ?? existing.label;
    const nextUrl = patch.url ?? existing.url;

    this.db
      .prepare("UPDATE webhooks SET label = ?, url = ? WHERE id = ?")
      .run(nextLabel, nextUrl, id);

    return { ...existing, label: nextLabel, url: nextUrl };
  }

  deleteWebhook(id: number): boolean {
    this.db.prepare("DELETE FROM routes WHERE webhook_id = ?").run(id);
    const result = this.db.prepare("DELETE FROM webhooks WHERE id = ?").run(id);
    return result.changes > 0;
  }

  clearWebhooks(): void {
    this.db.exec("DELETE FROM routes; DELETE FROM webhooks;");
  }

  listRoutes(): RouteRecord[] {
    const rows = this.db
      .prepare(
        `SELECT id, source_id, webhook_id, poll_interval_minutes, enabled,
                created_at, updated_at, last_run_at
         FROM routes ORDER BY id ASC`,
      )
      .all() as Array<{
        id: number;
        source_id: string;
        webhook_id: number;
        poll_interval_minutes: number;
        enabled: number;
        created_at: string;
        updated_at: string;
        last_run_at: string | null;
      }>;

    return rows.map((row) => ({
      id: row.id,
      sourceId: row.source_id,
      webhookId: row.webhook_id,
      pollIntervalMinutes: row.poll_interval_minutes,
      enabled: row.enabled === 1,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      lastRunAt: row.last_run_at,
    }));
  }

  getRoute(id: number): RouteRecord | undefined {
    const row = this.db
      .prepare(
        `SELECT id, source_id, webhook_id, poll_interval_minutes, enabled,
                created_at, updated_at, last_run_at
         FROM routes WHERE id = ?`,
      )
      .get(id) as
        | {
            id: number;
            source_id: string;
            webhook_id: number;
            poll_interval_minutes: number;
            enabled: number;
            created_at: string;
            updated_at: string;
            last_run_at: string | null;
          }
        | undefined;

    if (!row) {
      return undefined;
    }

    return {
      id: row.id,
      sourceId: row.source_id,
      webhookId: row.webhook_id,
      pollIntervalMinutes: row.poll_interval_minutes,
      enabled: row.enabled === 1,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      lastRunAt: row.last_run_at,
    };
  }

  createRoute(input: {
    sourceId: string;
    webhookId: number;
    pollIntervalMinutes: number;
    enabled: boolean;
  }): RouteRecord {
    const now = new Date().toISOString();
    const result = this.db
      .prepare(
        `INSERT INTO routes
           (source_id, webhook_id, poll_interval_minutes, enabled, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(
        input.sourceId,
        input.webhookId,
        input.pollIntervalMinutes,
        input.enabled ? 1 : 0,
        now,
        now,
      );

    return {
      id: Number(result.lastInsertRowid),
      sourceId: input.sourceId,
      webhookId: input.webhookId,
      pollIntervalMinutes: input.pollIntervalMinutes,
      enabled: input.enabled,
      createdAt: now,
      updatedAt: now,
      lastRunAt: null,
    };
  }

  updateRoute(
    id: number,
    patch: {
      sourceId?: string;
      webhookId?: number;
      pollIntervalMinutes?: number;
      enabled?: boolean;
    },
  ): RouteRecord | undefined {
    const existing = this.getRoute(id);
    if (!existing) {
      return undefined;
    }

    const next: RouteRecord = {
      ...existing,
      sourceId: patch.sourceId ?? existing.sourceId,
      webhookId: patch.webhookId ?? existing.webhookId,
      pollIntervalMinutes: patch.pollIntervalMinutes ?? existing.pollIntervalMinutes,
      enabled: patch.enabled ?? existing.enabled,
      updatedAt: new Date().toISOString(),
    };

    this.db
      .prepare(
        `UPDATE routes
           SET source_id = ?, webhook_id = ?, poll_interval_minutes = ?, enabled = ?, updated_at = ?
         WHERE id = ?`,
      )
      .run(
        next.sourceId,
        next.webhookId,
        next.pollIntervalMinutes,
        next.enabled ? 1 : 0,
        next.updatedAt,
        id,
      );

    return next;
  }

  deleteRoute(id: number): boolean {
    const result = this.db.prepare("DELETE FROM routes WHERE id = ?").run(id);
    return result.changes > 0;
  }

  markRouteRun(id: number, ranAt: string = new Date().toISOString()): void {
    this.db.prepare("UPDATE routes SET last_run_at = ? WHERE id = ?").run(ranAt, id);
  }

  getSetting(key: string): string | undefined {
    const row = this.db
      .prepare("SELECT value FROM app_settings WHERE key = ?")
      .get(key) as { value: string } | undefined;
    return row?.value;
  }

  setSetting(key: string, value: string | null): void {
    if (value === null) {
      this.db.prepare("DELETE FROM app_settings WHERE key = ?").run(key);
      return;
    }

    this.db
      .prepare(
        `INSERT INTO app_settings (key, value, updated_at)
         VALUES (?, ?, ?)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
      )
      .run(key, value, new Date().toISOString());
  }

  clearSetting(key: string): void {
    this.setSetting(key, null);
  }

  close(): void {
    this.db.close();
  }

  private initialize(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        rss_url TEXT NOT NULL,
        last_checked_at TEXT
      );

      CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        category TEXT NOT NULL,
        published_at TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        UNIQUE(source_id, url),
        FOREIGN KEY(source_id) REFERENCES sources(id)
      );

      CREATE TABLE IF NOT EXISTS deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        webhook_target TEXT,
        delivered_at TEXT NOT NULL,
        error_message TEXT,
        FOREIGN KEY(article_id) REFERENCES articles(id)
      );

      CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        url TEXT NOT NULL,
        created_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        webhook_id INTEGER NOT NULL,
        poll_interval_minutes INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_run_at TEXT,
        FOREIGN KEY(webhook_id) REFERENCES webhooks(id)
      );

      CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    `);
  }
}
