import { runTopArticleTest, runWorker } from "./app.ts";
import { getConfig } from "./config.ts";
import { loadEnvFile } from "./utils/env.ts";

loadEnvFile();

type CliConfig = {
  topMode: boolean;
  forceLatest: boolean;
  topCount?: number;
  focusUrl?: string;
};

const config = getConfig();
const argv = process.argv.slice(2);
const cli = parseCliConfig(argv);

if (cli.topMode) {
  const topTestCount = cli.forceLatest
    ? 1
    : (cli.topCount ?? config.topTestArticleCount);
  await runTopArticleTest(config, topTestCount, cli.focusUrl);
  process.exit(0);
}

await runWorker(config);

function parseCliConfig(argv: string[]): CliConfig {
  if (hasFlag(argv, "--help", "-h")) {
    printUsage();
    process.exit(0);
  }

  return {
    topMode: hasFlag(argv, "--top", "--test-top"),
    forceLatest: hasFlag(argv, "--latest"),
    topCount: parseCliNumber(argv, "--top-count", undefined),
    focusUrl: parseCliString(argv, "--focus-url"),
  };
}

function printUsage(): void {
  const message = [
    "Usage:",
    "  npm start                  # run worker (poll mode)",
    "  npm run top                # send top test articles",
    "  npm run top -- [options]   # options for single run",
    "",
    "Options:",
    "  --top, --test-top          run test mode (top article summary)",
    "  --top-count N               number of top items to send",
    "  --latest                    send only the latest 1 item",
    "  --focus-url <url>           prioritize a specific article URL",
    "  --help, -h                  show this message",
    "",
    "Examples:",
    "  npm run top -- --top-count 2 --focus-url https://openai.com/index/our-approach-to-the-model-spec/",
  ].join("\n");

  console.log(message);
}

function parseCliNumber(
  argv: string[],
  flag: string,
  fallback?: number,
  minimum = 1,
): number | undefined {
  const raw = parseCliValue(argv, flag);
  if (!raw) {
    if (fallback !== undefined) {
      return fallback;
    }

    return undefined;
  }

  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed < minimum) {
    throw new Error(`Invalid number for ${flag}: ${raw}. Minimum: ${minimum}`);
  }

  return parsed;
}

function hasFlag(argv: string[], ...flags: string[]): boolean {
  return flags.some((flag) => argv.includes(flag));
}

function parseCliValue(argv: string[], flag: string): string | undefined {
  const exactIndex = argv.findIndex((value) => value === flag);
  if (exactIndex >= 0) {
    const next = argv[exactIndex + 1];
    if (next && !next.startsWith("--")) {
      return next;
    }

    return undefined;
  }

  const prefixed = argv.find((value) => value.startsWith(`${flag}=`));
  if (!prefixed) {
    return undefined;
  }

  return prefixed.substring(`${flag}=`.length);
}

function parseCliString(argv: string[], flag: string): string | undefined {
  return parseCliValue(argv, flag);
}
