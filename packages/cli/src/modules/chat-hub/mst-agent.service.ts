import { Logger } from '@n8n/backend-common';
import { Service } from '@n8n/di';

const WORKFLOW_KEYWORDS = [
	'buatkan workflow',
	'buat workflow',
	'buatkan saya workflow',
	'buatkan automasi',
	'buat automasi',
	'buatkan otomasi',
	'buat otomasi',
	'create workflow',
	'build workflow',
	'tolong buatkan workflow',
	'buatkan alur',
	'buat alur otomatis',
];

interface AgentWorkflowResponse {
	message: string;
	workflow_name: string;
	workflow_id: string;
	workflow_url: string;
	steps: Array<{ step: number; node: string; description: string }>;
}

@Service()
export class MstAgentService {
	private readonly agentServiceUrl: string;

	constructor(private readonly logger: Logger) {
		this.agentServiceUrl = process.env.AGENT_SERVICE_URL ?? 'http://mst-agent-service:8000';
	}

	isWorkflowRequest(message: string): boolean {
		const lower = message.toLowerCase();
		return WORKFLOW_KEYWORDS.some((kw) => lower.includes(kw));
	}

	async buildWorkflow(
		prompt: string,
		userId: string,
		sessionId: string,
	): Promise<AgentWorkflowResponse> {
		const url = `${this.agentServiceUrl}/workflow/build`;

		this.logger.debug(`Calling Agent Service: ${url}`);

		const response = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ prompt, user_id: userId, session_id: sessionId }),
			signal: AbortSignal.timeout(90_000),
		});

		if (!response.ok) {
			const text = await response.text();
			throw new Error(`Agent Service error (${response.status}): ${text}`);
		}

		return (await response.json()) as AgentWorkflowResponse;
	}

	formatResponse(result: AgentWorkflowResponse): string {
		const steps = result.steps.map((s) => `${s.step}. **${s.node}** — ${s.description}`).join('\n');

		return [
			`✅ ${result.message}`,
			'',
			`**${result.workflow_name}**`,
			'',
			steps,
			'',
			`🔗 [Buka Workflow](${result.workflow_url})`,
		].join('\n');
	}
}
