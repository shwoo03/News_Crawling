import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

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
    `);
  }
}
