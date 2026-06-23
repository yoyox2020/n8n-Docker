import type {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class MistikaAiApi implements ICredentialType {
	name = 'mistikaAiApi';

	displayName = 'Mistika-AI';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			required: true,
			default: '',
		},
		{
			displayName: 'Base URL',
			name: 'url',
			type: 'string',
			required: true,
			default: 'https://misstika.mst.co.id/llm-router',
			description:
				'URL dasar tanpa path endpoint. Mistika: https://misstika.mst.co.id/llm-router | OpenRouter: https://openrouter.ai/api/v1',
		},
		{
			displayName: 'Auth Type',
			name: 'authType',
			type: 'options',
			options: [
				{
					name: 'x-api-key (Mistika internal)',
					value: 'x-api-key',
				},
				{
					name: 'Authorization: Bearer (OpenRouter / OpenAI)',
					value: 'bearer',
				},
			],
			default: 'x-api-key',
			description: 'Cara API key dikirim. Mistika pakai x-api-key, OpenRouter/OpenAI pakai Bearer.',
		},
		{
			displayName: 'Chat Path',
			name: 'chatPath',
			type: 'string',
			required: true,
			default: '/chat/streamchat',
			description:
				'Path endpoint chat. Mistika: /chat/streamchat | OpenRouter/OpenAI: /chat/completions',
		},
		{
			displayName: 'Default Model',
			name: 'defaultModel',
			type: 'string',
			default: '',
			placeholder: 'contoh: deepseek/deepseek-v4-flash',
			description:
				'Model yang dipakai saat test koneksi dan sebagai default. ' +
				'OpenRouter/OpenAI: wajib diisi, contoh deepseek/deepseek-v4-flash atau gpt-4o-mini. ' +
				'Mistika: isi nama model Mistika yang tersedia, atau kosongkan jika server auto-pilih model.',
		},
		{
			displayName: 'Skip SSL Verification',
			name: 'skipSslVerification',
			type: 'boolean',
			default: false,
			description:
				'Disable SSL certificate check. Enable for internal servers with self-signed certificates.',
		},
	];

	// authenticate dipakai oleh HTTP Request node biasa — bukan oleh LmChatMistikaAi
	// (node LmChatMistikaAi set header sendiri di supplyData)
	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				// Kirim header yang sesuai authType yang dipilih user
				Authorization:
					'={{ $credentials.authType === "x-api-key" ? "" : "Bearer " + $credentials.apiKey }}',
				'x-api-key': '={{ $credentials.authType === "x-api-key" ? $credentials.apiKey : "" }}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			// Base URL tidak boleh include path endpoint — hanya domain + prefix
			// Contoh benar: https://misstika.mst.co.id/llm-router
			baseURL: '={{ $credentials.url }}',
			// Chat Path adalah sisa path endpoint
			// Contoh benar untuk Mistika: /chat/streamchat
			url: '={{ $credentials.chatPath }}',
			method: 'POST',
			headers: {
				// Override auth header di test request agar sesuai authType
				Authorization:
					'={{ $credentials.authType === "x-api-key" ? "" : "Bearer " + $credentials.apiKey }}',
				'x-api-key': '={{ $credentials.authType === "x-api-key" ? $credentials.apiKey : "" }}',
			},
			body: {
				model: '={{ $credentials.defaultModel }}',
				messages: [{ role: 'user', content: 'ping' }],
				max_tokens: 1,
			},
			skipSslCertificateValidation: true,
		},
	};
}
