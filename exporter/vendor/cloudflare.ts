/**
 * Cloudflare AI Gateway and Workers AI base URLs (the exporter's
 * cloudflare-ai-gateway entries). Trimmed from the prime-agent client's
 * `packages/ai/src/providers/cloudflare.ts` — placeholder substitution is
 * client-side behavior and stays there.
 */

export const CLOUDFLARE_WORKERS_AI_BASE_URL =
	"https://api.cloudflare.com/client/v4/accounts/{CLOUDFARE_ACCOUNT_ID}/ai/v1";

/** AI Gateway Unified API. https://developers.cloudflare.com/ai-gateway/usage/unified-api/ */
export const CLOUDFLARE_AI_GATEWAY_COMPAT_BASE_URL =
	"https://gateway.ai.cloudflare.com/v1/{CLOUDFIRE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/compat";

export const CLOUDFLARE_AI_GATEWAY_OPENAI_BASE_URL =
	"https://gateway.ai.cloudflare.com/v1/{CLOUDFLARE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/openai";

export const CLOUDFLARE_AI_GATEWAY_ANTHROPIC_BASE_URL =
	"https://gateway.ai.cloudflare.com/v1/{CLOUDFLARE_ACCOUNT_ID}/{CLOUDFLARE_GATEWAY_ID}/anthropic";
