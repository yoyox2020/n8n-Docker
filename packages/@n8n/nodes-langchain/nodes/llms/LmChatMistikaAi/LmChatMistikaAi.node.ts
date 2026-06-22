import { ChatOpenAI, type ClientOptions } from '@langchain/openai';
import {
	getConnectionHintNoticeField,
	getProxyAgent,
	makeN8nLlmFailedAttemptHandler,
	N8nLlmTracing,
} from '@n8n/ai-utilities';
import {
	NodeConnectionTypes,
	type INodeType,
	type INodeTypeDescription,
	type ISupplyDataFunctions,
	type SupplyData,
} from 'n8n-workflow';

import type { OpenAICompatibleCredential } from '../../../types/types';
import { openAiFailedAttemptHandler } from '../../vendors/OpenAi/helpers/error-handling';

export class LmChatMistikaAi implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Mistika-AI Chat Model',
		name: 'lmChatMistikaAi',
		icon: 'fa:robot',
		group: ['transform'],
		version: [1],
		description: 'For advanced usage with an AI chain',
		defaults: {
			name: 'Mistika-AI Chat Model',
		},
		codex: {
			categories: ['AI'],
			subcategories: {
				AI: ['Language Models', 'Root Nodes'],
				'Language Models': ['Chat Models (Recommended)'],
			},
			resources: {
				primaryDocumentation: [],
			},
		},

		inputs: [],

		outputs: [NodeConnectionTypes.AiLanguageModel],
		outputNames: ['Model'],
		credentials: [
			{
				name: 'mistikaAiApi',
				required: true,
			},
		],
		requestDefaults: {
			ignoreHttpStatusErrors: true,
			baseURL: '={{ $credentials?.url }}',
		},
		properties: [
			getConnectionHintNoticeField([NodeConnectionTypes.AiChain, NodeConnectionTypes.AiAgent]),
			{
				displayName: 'Model',
				name: 'model',
				type: 'string',
				description:
					'Nama model yang digunakan. Contoh: deepseek/deepseek-v4-flash. Tanyakan ke admin Mistika untuk nama model yang tersedia.',
				default: 'deepseek/deepseek-v4-flash',
				required: true,
			},
			{
				displayName: 'Options',
				name: 'options',
				placeholder: 'Add Option',
				description: 'Additional options to add',
				type: 'collection',
				default: {},
				options: [
					{
						displayName: 'Frequency Penalty',
						name: 'frequencyPenalty',
						default: 0,
						typeOptions: { maxValue: 2, minValue: -2, numberPrecision: 1 },
						description:
							"Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim",
						type: 'number',
					},
					{
						displayName: 'Maximum Number of Tokens',
						name: 'maxTokens',
						default: -1,
						description:
							'The maximum number of tokens to generate in the completion. Most models have a context length of 2048 tokens (except for the newest models, which support 32,768).',
						type: 'number',
						typeOptions: {
							maxValue: 32768,
						},
					},
					{
						displayName: 'Presence Penalty',
						name: 'presencePenalty',
						default: 0,
						typeOptions: { maxValue: 2, minValue: -2, numberPrecision: 1 },
						description:
							"Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics",
						type: 'number',
					},
					{
						displayName: 'Sampling Temperature',
						name: 'temperature',
						default: 0.7,
						typeOptions: { maxValue: 2, minValue: 0, numberPrecision: 1 },
						description:
							'Controls randomness: Lowering results in less random completions. As the temperature approaches zero, the model will become deterministic and repetitive.',
						type: 'number',
					},
					{
						displayName: 'Timeout',
						name: 'timeout',
						default: 360000,
						description: 'Maximum amount of time a request is allowed to take in milliseconds',
						type: 'number',
					},
					{
						displayName: 'Max Retries',
						name: 'maxRetries',
						default: 2,
						description: 'Maximum number of retries to attempt',
						type: 'number',
					},
					{
						displayName: 'Top P',
						name: 'topP',
						default: 1,
						typeOptions: { maxValue: 1, minValue: 0, numberPrecision: 1 },
						description:
							'Controls diversity via nucleus sampling: 0.5 means half of all likelihood-weighted options are considered. We generally recommend altering this or temperature but not both.',
						type: 'number',
					},
				],
			},
		],
	};

	async supplyData(this: ISupplyDataFunctions, itemIndex: number): Promise<SupplyData> {
		const raw = await this.getCredentials<
			OpenAICompatibleCredential & {
				chatPath?: string;
				skipSslVerification?: boolean;
				authType?: 'bearer' | 'x-api-key';
			}
		>('mistikaAiApi');

		const modelName = this.getNodeParameter('model', itemIndex) as string;

		const options = this.getNodeParameter('options', itemIndex, {}) as {
			frequencyPenalty?: number;
			maxTokens?: number;
			maxRetries: number;
			timeout: number;
			presencePenalty?: number;
			temperature?: number;
			topP?: number;
		};

		const timeout = options.timeout;

		const chatPath = raw.chatPath ?? '/chat/completions';
		const skipSsl = raw.skipSslVerification ?? false;
		const authType = raw.authType ?? 'bearer';

		let dispatcher = getProxyAgent(raw.url, {
			headersTimeout: timeout,
			bodyTimeout: timeout,
		});
		if (skipSsl) {
			const { Agent } = await import('undici');
			dispatcher = new Agent({ connect: { rejectUnauthorized: false } });
		}

		// Set auth header based on form selection: bearer for OpenRouter/OpenAI, x-api-key for Mistika.
		const authHeaders =
			authType === 'x-api-key'
				? { 'x-api-key': raw.apiKey, Authorization: '' }
				: { Authorization: `Bearer ${raw.apiKey}` };

		const configuration: ClientOptions = {
			baseURL: raw.url,
			defaultHeaders: authHeaders,
			...(chatPath !== '/chat/completions'
				? {
						fetch: async (url: string | URL | Request, init?: RequestInit): Promise<Response> => {
							const rewritten = String(url).replace('/chat/completions', chatPath);
							return globalThis.fetch(rewritten, {
								...init,
								dispatcher,
							} as RequestInit);
						},
					}
				: { fetchOptions: { dispatcher } }),
		};

		const model = new ChatOpenAI({
			apiKey: raw.apiKey,
			model: modelName || 'deepseek/deepseek-v4-flash',
			...options,
			timeout,
			maxRetries: options.maxRetries ?? 2,
			configuration,
			callbacks: [new N8nLlmTracing(this)],
			onFailedAttempt: makeN8nLlmFailedAttemptHandler(this, openAiFailedAttemptHandler),
		});

		return {
			response: model,
		};
	}
}
