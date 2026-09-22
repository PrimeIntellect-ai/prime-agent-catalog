/**
 * The catalog-data type graph the exporter needs: APIs, providers, thinking
 * levels, compat records, and the Model shape. Trimmed from the
 * prime-agent client's `packages/ai/src/types.ts` — this file is
 * type-only (erased at runtime) and carries no client behavior.
 */


export type KnownApi =
	| "openai-completions"
	| "mistral-conversations"
	| "openai-responses"
	| "azure-openai-responses"
	| "openai-codex-responses"
	| "anthropic-messages"
	| "bedrock-converse-stream"
	| "google-generative-ai"
	| "google-vertex";

export type Api = KnownApi | (string & {});

export type KnownProvider =
	| "amazon-bedrock"
	| "anthropic"
	| "google"
	| "google-vertex"
	| "openai"
	| "azure-openai-responses"
	| "openai-codex"
	| "prime-inference"
	| "deepseek"
	| "github-copilot"
	| "xai"
	| "groq"
	| "cerebras"
	| "openrouter"
	| "vercel-ai-gateway"
	| "zai"
	| "mistral"
	| "minimax"
	| "minimax-cn"
	| "moonshotai"
	| "moonshotai-cn"
	| "huggingface"
	| "fireworks"
	| "opencode"
	| "opencode-go"
	| "kimi-coding"
	| "cloudflare-workers-ai"
	| "cloudflare-ai-gateway"
	| "xiaomi"
	| "xiaomi-token-plan-cn"
	| "xiaomi-token-plan-ams"
	| "xiaomi-token-plan-sgp";

export type Provider = KnownProvider | string;

export type ThinkingLevel = "minimal" | "low" | "medium" | "high" | "xhigh" | "max";

export type ModelThinkingLevel = "off" | ThinkingLevel;

export type ThinkingLevelMap = Partial<Record<ModelThinkingLevel, string | null>>;

/** Token budgets for each thinking level (token-based providers only) */

export interface OpenAICompletionsCompat {
	/** Whether the provider supports the `store` field. Default: auto-detected from URL. */
	supportsStore?: boolean;
	/** Whether the provider supports the `developer` role (vs `system`). Default: auto-detected from URL. */
	supportsDeveloperRole?: boolean;
	/** Whether the provider supports `reasoning_effort`. Default: auto-detected from URL. */
	supportsReasoningEffort?: boolean;
	/** Whether the provider supports `stream_options: { include_usage: true }` for token usage in streaming responses. Default: true. */
	supportsUsageInStreaming?: boolean;
	/** Which field to use for max tokens. Default: auto-detected from URL. */
	maxTokensField?: "max_completion_tokens" | "max_tokens";
	/** Whether tool results require the `name` field. Default: auto-detected from URL. */
	requiresToolResultName?: boolean;
	/** Whether a user message after tool results requires an assistant message in between. Default: auto-detected from URL. */
	requiresAssistantAfterToolResult?: boolean;
	/** Whether thinking blocks must be converted to text blocks with <thinking> delimiters. Default: auto-detected from URL. */
	requiresThinkingAsText?: boolean;
	/** Whether all replayed assistant messages must include an empty reasoning_content field when reasoning is enabled. Default: auto-detected from URL. */
	requiresReasoningContentOnAssistantMessages?: boolean;
	/** Format for reasoning/thinking parameter. "openai" uses reasoning_effort, "openrouter" uses reasoning: { effort }, "deepseek" uses thinking: { type } plus reasoning_effort, "zai" uses top-level enable_thinking: boolean, "qwen" uses top-level enable_thinking: boolean, and "qwen-chat-template" uses chat_template_kwargs.enable_thinking. Default: "openai". */
	thinkingFormat?: "openai" | "openrouter" | "deepseek" | "zai" | "qwen" | "qwen-chat-template";
	/** OpenRouter-specific routing preferences. Only used when baseUrl points to OpenRouter. */
	openRouterRouting?: OpenRouterRouting;
	/** Vercel AI Gateway routing preferences. Only used when baseUrl points to Vercel AI Gateway. */
	vercelGatewayRouting?: VercelGatewayRouting;
	/** Whether z.ai supports top-level `tool_stream: true` for streaming tool call deltas. Default: false. */
	zaiToolStream?: boolean;
	/** Whether the provider supports the `strict` field in tool definitions. Default: true. */
	supportsStrictMode?: boolean;
	/** Cache control convention for prompt caching. "anthropic" applies Anthropic-style `cache_control` markers to the system prompt, last tool definition, and last user/assistant text content. */
	cacheControlFormat?: "anthropic";
	/** Whether to send known session-affinity headers (`session_id`, `x-client-request-id`, `x-session-affinity`) from `options.sessionId` when caching is enabled. Default: false. */
	sendSessionAffinityHeaders?: boolean;
	/** Whether the provider supports long prompt cache retention (`prompt_cache_retention: "24h"` or Anthropic-style `cache_control.ttl: "1h"`, depending on format). Default: true. */
	supportsLongCacheRetention?: boolean;
}

/** Compatibility settings for OpenAI Responses APIs. */

export interface OpenAIResponsesCompat {
	/** Whether to send the OpenAI `session_id` cache-affinity header from `options.sessionId` when caching is enabled. Default: true. */
	sendSessionIdHeader?: boolean;
	/** Whether the provider supports `prompt_cache_retention: "24h"`. Default: true. */
	supportsLongCacheRetention?: boolean;
}

/** Compatibility settings for Anthropic Messages-compatible APIs. */

export interface AnthropicMessagesCompat {
	/**
	 * Whether the provider accepts per-tool `eager_input_streaming`.
	 * When false, the Anthropic provider omits `tools[].eager_input_streaming`
	 * and sends the legacy `fine-grained-tool-streaming-2025-05-14` beta header
	 * for tool-enabled requests.
	 * Default: true.
	 */
	supportsEagerToolInputStreaming?: boolean;
	/** Whether the provider supports Anthropic long cache retention (`cache_control.ttl: "1h"`). Default: true. */
	supportsLongCacheRetention?: boolean;
}

/**
 * OpenRouter provider routing preferences.
 * Controls which upstream providers OpenRouter routes requests to.
 * Sent as the `provider` field in the OpenRouter API request body.
 * @see https://openrouter.ai/docs/guides/routing/provider-selection
 */

export interface OpenRouterRouting {
	/** Whether to allow backup providers to serve requests. Default: true. */
	allow_fallbacks?: boolean;
	/** Whether to filter providers to only those that support all parameters in the request. Default: false. */
	require_parameters?: boolean;
	/** Data collection setting. "allow" (default): allow providers that may store/train on data. "deny": only use providers that don't collect user data. */
	data_collection?: "deny" | "allow";
	/** Whether to restrict routing to only ZDR (Zero Data Retention) endpoints. */
	zdr?: boolean;
	/** Whether to restrict routing to only models that allow text distillation. */
	enforce_distillable_text?: boolean;
	/** An ordered list of provider names/slugs to try in sequence, falling back to the next if unavailable. */
	order?: string[];
	/** List of provider names/slugs to exclusively allow for this request. */
	only?: string[];
	/** List of provider names/slugs to skip for this request. */
	ignore?: string[];
	/** A list of quantization levels to filter providers by (e.g., ["fp16", "bf16", "fp8", "fp6", "int8", "int4", "fp4", "fp32"]). */
	quantizations?: string[];
	/** Sorting strategy. Can be a string (e.g., "price", "throughput", "latency") or an object with `by` and `partition`. */
	sort?:
		| string
		| {
				/** The sorting metric: "price", "throughput", "latency". */
				by?: string;
				/** Partitioning strategy: "model" (default) or "none". */
				partition?: string | null;
		  };
	/** Maximum price per million tokens (USD). */
	max_price?: {
		/** Price per million prompt tokens. */
		prompt?: number | string;
		/** Price per million completion tokens. */
		completion?: number | string;
		/** Price per image. */
		image?: number | string;
		/** Price per audio unit. */
		audio?: number | string;
		/** Price per request. */
		request?: number | string;
	};
	/** Preferred minimum throughput (tokens/second). Can be a number (applies to p50) or an object with percentile-specific cutoffs. */
	preferred_min_throughput?:
		| number
		| {
				/** Minimum tokens/second at the 50th percentile. */
				p50?: number;
				/** Minimum tokens/second at the 75th percentile. */
				p75?: number;
				/** Minimum tokens/second at the 90th percentile. */
				p90?: number;
				/** Minimum tokens/second at the 99th percentile. */
				p99?: number;
		  };
	/** Preferred maximum latency (seconds). Can be a number (applies to p50) or an object with percentile-specific cutoffs. */
	preferred_max_latency?:
		| number
		| {
				/** Maximum latency in seconds at the 50th percentile. */
				p50?: number;
				/** Maximum latency in seconds at the 75th percentile. */
				p75?: number;
				/** Maximum latency in seconds at the 90th percentile. */
				p90?: number;
				/** Maximum latency in seconds at the 99th percentile. */
				p99?: number;
		  };
}

/**
 * Vercel AI Gateway routing preferences.
 * Controls which upstream providers the gateway routes requests to.
 * @see https://vercel.com/docs/ai-gateway/models-and-providers/provider-options
 */

export interface VercelGatewayRouting {
	/** List of provider slugs to exclusively use for this request (e.g., ["bedrock", "anthropic"]). */
	only?: string[];
	/** List of provider slugs to try in order (e.g., ["anthropic", "openai"]). */
	order?: string[];
}

// Model interface for the unified model system

export interface Model<TApi extends Api> {
	id: string;
	name: string;
	api: TApi;
	provider: Provider;
	baseUrl: string;
	reasoning: boolean;
	/**
	 * Maps pi thinking levels to provider/model-specific values.
	 * Missing keys use provider defaults. null marks a level as unsupported.
	 */
	thinkingLevelMap?: ThinkingLevelMap;
	input: ("text" | "image")[];
	cost: {
		input: number; // $/million tokens
		output: number; // $/million tokens
		cacheRead: number; // $/million tokens
		cacheWrite: number; // $/million tokens
	};
	contextWindow: number;
	maxTokens: number;
	/** Flagship model surfaced above non-featured models of the same provider in pickers. */
	featured?: boolean;
	headers?: Record<string, string>;
	/** Compatibility overrides for OpenAI-compatible APIs. If not set, auto-detected from baseUrl. */
	compat?: TApi extends "openai-completions"
		? OpenAICompletionsCompat
		: TApi extends "openai-responses"
			? OpenAIResponsesCompat
			: TApi extends "anthropic-messages"
				? AnthropicMessagesCompat
				: never;
}
