import { Logger } from '@n8n/backend-common';
import { Service } from '@n8n/di';

// ===== TIPE DATA =====

interface ToolSuggestion {
	node_type: string;
	display_name: string;
	description: string;
	category: 'trigger' | 'action' | 'logic';
}

interface SuggestToolsResponse {
	triggers: ToolSuggestion[];
	actions: ToolSuggestion[];
	logic: ToolSuggestion[];
	total: number;
}

interface PendingWorkflow {
	prompt: string;
	userId: string;
	expiresAt: number;
}

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
	// Agent AI juga diarahkan ke workflow builder
	'buatkan agent',
	'buat agent',
	'buatkan ai agent',
	'buat ai agent',
	'create agent',
	'build agent',
	// Revisi / ubah workflow yang sudah ada
	'revisi workflow',
	'revisi agent',
	'revisi alur',
	'perbaiki workflow',
	'ubah workflow',
	'ganti workflow',
	'update workflow',
	// English revision with context
	'revise workflow',
	'revise agent',
	'modify workflow',
	'modify agent',
	'change workflow',
	'update the workflow',
	'fix the workflow',
];

const REVISION_KEYWORDS = [
	// Indonesia
	'revisi',
	'perbaiki',
	'ubah',
	'ganti',
	'modifikasi',
	// English
	'revise',
	'modify',
	'change',
	'edit',
	'update',
	'redo',
	'fix',
	'remake',
	'adjust',
];

@Service()
export class MstAgentService {
	private static readonly PENDING_TTL_MS = 10 * 60 * 1000; // 10 menit

	private readonly agentServiceUrl: string;

	/** Menyimpan workflow request yang menunggu konfirmasi user (per session). */
	private readonly pendingWorkflows = new Map<string, PendingWorkflow>();

	constructor(private readonly logger: Logger) {
		this.agentServiceUrl = process.env.AGENT_SERVICE_URL ?? 'http://mst-agent-service:8000';
	}

	// ===== DETEKSI INTENT =====

	isWorkflowRequest(message: string): boolean {
		const lower = message.toLowerCase();
		return WORKFLOW_KEYWORDS.some((kw) => lower.includes(kw));
	}

	/** Cek apakah pesan user adalah konfirmasi singkat ("lanjut", "ya", "ok lanjut", dll). */
	isConfirmation(message: string): boolean {
		const trimmed = message
			.trim()
			.toLowerCase()
			.replace(/[.,!?]+$/, '');
		const CONFIRM_WORDS = [
			'lanjut',
			'ya',
			'oke',
			'ok',
			'setuju',
			'proceed',
			'yes',
			'buat',
			'buatkan',
			'jalankan',
			'lakukan',
			'gas',
			'siap',
		];
		// Cocok jika pesan hanya terdiri dari kata-kata konfirmasi (1–3 kata)
		const words = trimmed.split(/\s+/);
		return words.length <= 3 && words.every((w) => CONFIRM_WORDS.includes(w));
	}

	/**
	 * Cek apakah pesan adalah permintaan revisi singkat ("revisi", "ubah", dll) tanpa detail.
	 * Jika ya, sistem harus meminta user menjelaskan revisinya.
	 */
	isRevisionRequest(message: string): boolean {
		const trimmed = message
			.trim()
			.toLowerCase()
			.replace(/[.,!?]+$/, '');
		const words = trimmed.split(/\s+/);
		return words.length <= 3 && REVISION_KEYWORDS.some((kw) => words[0] === kw);
	}

	// ===== PENDING WORKFLOW STATE =====

	hasPendingWorkflow(sessionId: string): boolean {
		const pending = this.pendingWorkflows.get(sessionId);
		if (!pending) return false;
		if (Date.now() > pending.expiresAt) {
			this.pendingWorkflows.delete(sessionId);
			return false;
		}
		return true;
	}

	savePendingWorkflow(sessionId: string, prompt: string, userId: string): void {
		this.pendingWorkflows.set(sessionId, {
			prompt,
			userId,
			expiresAt: Date.now() + MstAgentService.PENDING_TTL_MS,
		});
	}

	/** Ambil dan hapus pending workflow (sekali pakai). */
	popPendingWorkflow(sessionId: string): PendingWorkflow | undefined {
		const pending = this.pendingWorkflows.get(sessionId);
		this.pendingWorkflows.delete(sessionId);
		if (pending && Date.now() > pending.expiresAt) return undefined;
		return pending;
	}

	clearPendingWorkflow(sessionId: string): void {
		this.pendingWorkflows.delete(sessionId);
	}

	// ===== TOOL SUGGESTION =====

	/** Tanyakan ke agent service node apa yang relevan untuk prompt ini (tanpa memanggil LLM). */
	async suggestTools(prompt: string): Promise<SuggestToolsResponse> {
		const url = `${this.agentServiceUrl}/workflow/tools`;
		const response = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ prompt }),
			signal: AbortSignal.timeout(30_000),
		});

		if (!response.ok) {
			throw new Error(`Tool suggestion failed (${response.status})`);
		}

		return (await response.json()) as SuggestToolsResponse;
	}

	/** Format daftar tool suggestion menjadi pesan chat yang informatif. */
	formatToolSuggestions(result: SuggestToolsResponse): string {
		const lines: string[] = ['Saya menemukan tools yang relevan untuk permintaan Anda:', ''];

		if (result.triggers.length > 0) {
			lines.push('🔵 **Trigger** (pemicu workflow):');
			for (const t of result.triggers.slice(0, 4)) {
				lines.push(`   • **${t.display_name}** — ${t.description}`);
			}
			lines.push('');
		}

		if (result.actions.length > 0) {
			lines.push('⚡ **Aksi** (integrasi yang akan dijalankan):');
			for (const a of result.actions.slice(0, 6)) {
				lines.push(`   • **${a.display_name}** — ${a.description}`);
			}
			lines.push('');
		}

		if (result.logic.length > 0) {
			lines.push('🔧 **Logic** (kondisi & transformasi data):');
			for (const l of result.logic.slice(0, 3)) {
				lines.push(`   • **${l.display_name}** — ${l.description}`);
			}
			lines.push('');
		}

		if (result.total === 0) {
			lines.push(
				'_Belum ditemukan tools spesifik — saya akan menggunakan node umum (Webhook, HTTP Request, Set)._',
			);
			lines.push('');
		}

		lines.push('---');
		lines.push(
			'Ketik **`lanjut`** untuk membuat workflow dengan tools di atas, ' +
				'atau sebutkan integrasi lain yang Anda butuhkan (misalnya: "tambahkan Slack dan Gmail").',
		);

		return lines.join('\n');
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
			// 5 menit — beri ruang untuk LLM lokal (Ollama) yang butuh lebih lama dari remote API
			signal: AbortSignal.timeout(300_000),
		});

		if (!response.ok) {
			const text = await response.text();
			// Ambil field "detail" dari JSON response FastAPI jika ada (pesan ramah untuk user)
			try {
				const json = JSON.parse(text) as { detail?: string };
				if (json.detail) throw new Error(json.detail);
			} catch (parseErr) {
				if (!(parseErr instanceof SyntaxError)) throw parseErr;
			}
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

	// ===== DETEKSI RESPONS APPROVAL DARI CHAT =====

	/**
	 * Cek apakah pesan user adalah respons terhadap approval request.
	 * Format: "setuju <uuid>" atau "tolak <uuid>"
	 */
	parseApprovalResponse(
		message: string,
	):
		| { isApproval: true; id: string; decision: 'approved' | 'rejected' }
		| { isApproval: false; hint?: string } {
		const trimmed = message.trim();
		const match = trimmed.match(
			/^(setuju|approve|ok|ya|lanjut|tolak|reject|batal|tidak)\s+([0-9a-f-]{36})\s*$/i,
		);
		if (match) {
			const keyword = match[1].toLowerCase();
			const id = match[2];
			const decision = ['setuju', 'approve', 'ok', 'ya', 'lanjut'].includes(keyword)
				? 'approved'
				: 'rejected';
			return { isApproval: true, id, decision };
		}

		// User ketik "setuju"/"approve"/"tolak"/"reject" tanpa ID — beri petunjuk
		const hintMatch = trimmed.match(/^(setuju|approve|tolak|reject|batal|cancel)\s*$/i);
		if (hintMatch) {
			return {
				isApproval: false,
				hint: 'Untuk menyetujui atau menolak, sertakan ID-nya:\n`setuju <ID>` atau `tolak <ID>`\n\nTo approve or reject, include the ID:\n`approve <ID>` or `reject <ID>`\n\nContoh/Example: `setuju 73a9f63b-e39f-4a28-8bbe-075c69389abc`',
			};
		}

		return { isApproval: false };
	}

	/**
	 * Format daftar approval pending menjadi pesan teks yang ditampilkan di chat.
	 * Dipanggil setelah workflow selesai dibuat, untuk memberi tahu user jika ada approval menunggu.
	 */
	formatApprovalNotification(approvals: ApprovalRequest[]): string {
		if (approvals.length === 0) return '';

		const riskEmoji = (level: string) =>
			({ critical: '🔴', high: '🟠', medium: '🟡', low: '🟢' })[level] ?? '⚪';

		const lines = ['', '---', '⚠️ **Ada permintaan persetujuan yang menunggu:**', ''];

		for (const ap of approvals) {
			lines.push(`${riskEmoji(ap.risk_level)} **${ap.node_name}**`);
			lines.push(`> ${ap.action_description}`);
			lines.push(`> Risiko: **${ap.risk_level}** | ID: \`${ap.id}\``);
			lines.push('');
		}

		lines.push(
			'Balas dengan **`setuju <ID>`** untuk mengizinkan atau **`tolak <ID>`** untuk membatalkan.',
		);

		return lines.join('\n');
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
