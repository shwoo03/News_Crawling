import type { ArticleContent, DiscordDeliveryResult, FetchLike, SummaryResult } from "../types.ts";

const DISCORD_DESCRIPTION_LIMIT = 4000;
const DISCORD_FIELD_VALUE_LIMIT = 1000;

export class DiscordNotifier {
  constructor(
    private readonly webhookUrl: string | undefined,
    private readonly fetchImpl: FetchLike = fetch,
  ) {}

  async send(article: ArticleContent, summary: SummaryResult): Promise<DiscordDeliveryResult> {
    if (!this.webhookUrl) {
      return {
        status: "skipped",
        reason: "Discord webhook is not configured.",
      };
    }

    const payload = {
      embeds: [
        {
          title: formatBriefingTitle(article.sourceName),
          url: article.url,
          description: formatBriefingDescription(summary),
          color: 0x10a37f,
          fields: [
            {
              name: "한눈에 보기",
              value: truncateDiscordValue(formatBullets(summary.briefing.highlights), DISCORD_FIELD_VALUE_LIMIT),
              inline: false,
            },
            {
              name: "왜 중요할까",
              value: truncateDiscordValue(formatBullets(summary.briefing.importance), DISCORD_FIELD_VALUE_LIMIT),
              inline: false,
            },
            {
              name: "출처",
              value: truncateDiscordValue(article.sourceName, DISCORD_FIELD_VALUE_LIMIT),
              inline: true,
            },
            {
              name: "발행 시각",
              value: truncateDiscordValue(formatPublishedAt(article.publishedAt), DISCORD_FIELD_VALUE_LIMIT),
              inline: true,
            },
          ],
        },
      ],
    };

    const response = await this.fetchImpl(this.webhookUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Discord webhook failed with status ${response.status}: ${errorText}`);
    }

    return { status: "sent" };
  }
}

function formatBriefingTitle(sourceName: string): string {
  return sourceName.endsWith("뉴스") ? `${sourceName} 브리핑` : `${sourceName} 뉴스 브리핑`;
}

function formatBriefingDescription(summary: SummaryResult): string {
  const description = [
    summary.briefing.lead,
    "",
    ...summary.briefing.summary,
  ].join("\n").trim();

  return truncateDiscordValue(description, DISCORD_DESCRIPTION_LIMIT);
}

function formatBullets(items: string[]): string {
  return items.map((item) => `• ${item}`).join("\n");
}

function formatPublishedAt(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function truncateDiscordValue(value: string, limit: number): string {
  if (value.length <= limit) {
    return value;
  }

  return `${value.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}
