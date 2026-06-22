import { Logger } from '@n8n/backend-common';
import { Service } from '@n8n/di';

// ===== TIPE DATA =====

interface AgentWorkflowResponse {
	message: string;
	workflow_name: string;
	workflow_id: string;
	workflow_url: string;
	steps: Array<{ step: number; node: string; description: string }>;
}

export interface ApprovalRequest {
	id: string;
	user_id: string;
	node_name: string;
	action_description: string;
	risk_level: string;
	status: string; // pending / approved / rejected / expired
	context: Record<string, unknown> | null;
	requested_at: string;
	responded_at: string | null;
	response_note: string | null;
}

export interface LastActivity {
	user_id: string;
	recent_workflows: Array<{
		id: number;
		workflow_id: string;
		workflow_name: string;
		workflow_url: string;
		step_count: number;
		original_prompt: string;
		created_at: string;
	}>;
	pending_approvals: Array<{
		id: string;
		node_name: string;
		action_description: string;
		risk_level: string;
		requested_at: string;
	}>;
}

// ===== KEYWORD DETEKSI WORKFLOW =====

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

@Service()
export class MstAgentService {
	private readonly agentServiceUrl: string;

	constructor(private readonly logger: Logger) {
		this.agentServiceUrl = process.env.AGENT_SERVICE_URL ?? 'http://mst-agent-service:8000';
	}

	// ===== DETEKSI INTENT =====

	isWorkflowRequest(message: string): boolean {
		const lower = message.toLowerCase();
		return WORKFLOW_KEYWORDS.some((kw) => lower.includes(kw));
	}

	// ===== WORKFLOW BUILDER =====

	async buildWorkflow(
		prompt: string,
		userId: string,
		sessionId: string,
	): Promise<AgentWorkflowResponse> {
		const url = `${this.agentServiceUrl}/workflow/build`;
		this.logger.debug(`[MstAgent] buildWorkflow → ${url}`);

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

	// ===== APPROVAL =====

	/** Ambil detail satu approval request berdasarkan ID-nya. */
	async getApproval(approvalId: string): Promise<ApprovalRequest> {
		const url = `${this.agentServiceUrl}/approval/${approvalId}`;
		const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });

		if (!response.ok) {
			const text = await response.text();
			throw new Error(`Approval fetch error (${response.status}): ${text}`);
		}

		return (await response.json()) as ApprovalRequest;
	}

	/** User memberikan keputusan: 'approved' atau 'rejected'. */
	async respondApproval(
		approvalId: string,
		decision: 'approved' | 'rejected',
		note?: string,
	): Promise<ApprovalRequest> {
		const url = `${this.agentServiceUrl}/approval/${approvalId}/respond`;
		this.logger.debug(`[MstAgent] respondApproval ${approvalId} → ${decision}`);

		const response = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ decision, note }),
			signal: AbortSignal.timeout(10_000),
		});

		if (!response.ok) {
			const text = await response.text();
			throw new Error(`Approval respond error (${response.status}): ${text}`);
		}

		return (await response.json()) as ApprovalRequest;
	}

	/** Ambil semua approval pending milik seorang user. */
	async listPendingApprovals(userId: string): Promise<ApprovalRequest[]> {
		const url = `${this.agentServiceUrl}/approval/user/${userId}?status=pending`;
		const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });

		if (!response.ok) return [];
		return (await response.json()) as ApprovalRequest[];
	}

	// ===== AKTIVITAS TERAKHIR =====

	/** Ambil workflow terakhir + approval pending milik user untuk sidebar. */
	async getLastActivity(userId: string): Promise<LastActivity> {
		const url = `${this.agentServiceUrl}/memory/${userId}/last-activity`;
		this.logger.debug(`[MstAgent] getLastActivity → ${url}`);

		const response = await fetch(url, { signal: AbortSignal.timeout(10_000) });

		if (!response.ok) {
			return { user_id: userId, recent_workflows: [], pending_approvals: [] };
		}

		return (await response.json()) as LastActivity;
	}
}
