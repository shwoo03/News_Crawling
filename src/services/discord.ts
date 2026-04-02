import type { ArticleContent, DiscordDeliveryResult, FetchLike, SummaryResult } from "../types.ts";

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
          title: article.title,
          url: article.url,
          description: summary.summaryKo,
          color: 0x10a37f,
          fields: [
            {
              name: "Source",
              value: article.sourceName,
              inline: true,
            },
            {
              name: "Published",
              value: formatPublishedAt(article.publishedAt),
              inline: true,
            },
            {
              name: "Link",
              value: article.url,
              inline: false,
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

function formatPublishedAt(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}
