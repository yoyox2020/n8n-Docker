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
			default: 'https://openrouter.ai/api/v1',
		},
		{
			displayName: 'Auth Type',
			name: 'authType',
			type: 'options',
			options: [
				{
					name: 'Authorization: Bearer (OpenRouter / OpenAI)',
					value: 'bearer',
				},
				{
					name: 'x-api-key (Mistika internal)',
					value: 'x-api-key',
				},
			],
			default: 'bearer',
			description: 'How the API key is sent to the provider.',
		},
		{
			displayName: 'Chat Path',
			name: 'chatPath',
			type: 'string',
			required: true,
			default: '/chat/completions',
			description:
				'Endpoint path. Use /chat/completions for OpenRouter/OpenAI. Use /chat/streamchat for Mistika.',
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

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{ $credentials.url }}',
			url: '={{ $credentials.chatPath }}',
			method: 'POST',
			body: {
				messages: [{ role: 'user', content: 'ping' }],
			},
			skipSslCertificateValidation: true,
		},
	};
}
