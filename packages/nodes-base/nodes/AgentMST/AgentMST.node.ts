import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

/**
 * MST Agent Node
 *
 * Node ini ditempatkan di dalam workflow n8n. Ketika workflow mencapai node ini,
 * Agent Service dipanggil untuk membuat keputusan berdasarkan AI.
 *
 * Tiga kemungkinan output:
 *   1. "decided"        — AI memutuskan aksi yang aman, workflow dilanjutkan
 *   2. "needs_approval" — AI menilai risiko tinggi, menunggu persetujuan user
 *   3. "error"          — AI tidak bisa memutuskan, workflow dihentikan dengan pesan error
 */
export class AgentMST implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'MST Agent',
		name: 'agentMST',
		icon: 'fa:robot',
		group: ['transform'],
		version: 1,
		description:
			'Buat keputusan runtime menggunakan AI Agent. Workflow akan pause jika butuh persetujuan.',
		defaults: {
			name: 'MST Agent',
		},
		codex: {
			categories: ['AI'],
			subcategories: {
				AI: ['Agents'],
			},
			alias: ['agent', 'ai', 'mst', 'decision'],
		},
		// Satu input dari node sebelumnya
		inputs: [NodeConnectionTypes.Main],
		// Tiga output dengan label jelas
		outputs: [NodeConnectionTypes.Main, NodeConnectionTypes.Main, NodeConnectionTypes.Main],
		outputNames: ['decided', 'needs_approval', 'error'],
		properties: [
			// --- Instruksi untuk AI ---
			{
				displayName: 'Instruksi untuk Agent',
				name: 'instruction',
				type: 'string',
				typeOptions: { rows: 4 },
				default: '',
				required: true,
				placeholder: 'Contoh: Periksa data pesanan dan putuskan apakah perlu dikirim ulang',
				description: 'Jelaskan ke AI apa yang harus diputuskan berdasarkan data input yang masuk',
			},
			// --- Pilihan aksi ---
			{
				displayName: 'Aksi yang Tersedia',
				name: 'availableActions',
				type: 'fixedCollection',
				typeOptions: { multipleValues: true },
				default: {},
				description: 'Daftarkan pilihan aksi yang boleh dipilih oleh AI',
				options: [
					{
						name: 'actions',
						displayName: 'Aksi',
						values: [
							{
								displayName: 'Nama Aksi',
								name: 'action',
								type: 'string',
								default: '',
								placeholder: 'Contoh: kirim_email / hapus_data / skip',
								description: 'Nama aksi singkat tanpa spasi',
							},
						],
					},
				],
			},
			// --- Konfigurasi Agent Service ---
			{
				displayName: 'URL Agent Service',
				name: 'agentServiceUrl',
				type: 'string',
				default: 'http://mst-agent-service:8000',
				description: 'URL base Agent Service. Jika running lokal: http://localhost:8000',
			},
			{
				displayName: 'User ID',
				name: 'userId',
				type: 'string',
				default: '={{ $("Set").item.json.user_id ?? "default_user" }}',
				description: 'ID user yang menjalankan workflow. Dipakai untuk notifikasi approval.',
			},
			// --- Timeout untuk approval ---
			{
				displayName: 'Timeout Approval (detik)',
				name: 'approvalTimeoutSeconds',
				type: 'number',
				default: 300,
				description: 'Berapa lama menunggu approval sebelum dianggap expired (default 5 menit)',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();

		// Output array: [decided[], needs_approval[], error[]]
		const decidedItems: INodeExecutionData[] = [];
		const needsApprovalItems: INodeExecutionData[] = [];
		const errorItems: INodeExecutionData[] = [];

		for (let i = 0; i < items.length; i++) {
			const instruction = this.getNodeParameter('instruction', i) as string;
			const agentServiceUrl = this.getNodeParameter('agentServiceUrl', i) as string;
			const userId = this.getNodeParameter('userId', i) as string;
			const approvalTimeoutSeconds = this.getNodeParameter('approvalTimeoutSeconds', i) as number;

			// Ambil daftar aksi dari fixedCollection
			const actionsCollection = this.getNodeParameter('availableActions', i) as IDataObject;
			const actionsList = (actionsCollection.actions as Array<{ action: string }>) ?? [];
			const availableActions = actionsList.map((a) => a.action).filter(Boolean);

			// Data dari node sebelumnya dijadikan input_data
			const inputData = items[i].json;

			const executionId = this.getExecutionId();
			const workflowId = this.getWorkflow().id?.toString() ?? undefined;

			try {
				// --- Langkah 1: Minta keputusan dari Agent Service ---
				const decideResponse = await fetch(`${agentServiceUrl}/runtime/decide`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						user_id: userId,
						execution_id: executionId,
						workflow_id: workflowId,
						node_name: this.getNode().name,
						instruction,
						input_data: inputData,
						available_actions: availableActions,
					}),
					signal: AbortSignal.timeout(30_000),
				});

				if (!decideResponse.ok) {
					const errorText = await decideResponse.text();
					throw new NodeOperationError(
						this.getNode(),
						`Agent Service error (${decideResponse.status}): ${errorText}`,
					);
				}

				const decision = (await decideResponse.json()) as {
					output: string;
					chosen_action?: string;
					reason: string;
					risk_level: string;
					approval_id?: string;
					error?: string;
				};

				// --- Langkah 2: Routing berdasarkan keputusan AI ---
				if (decision.output === 'decided') {
					// AI langsung memutuskan — teruskan ke output pertama
					decidedItems.push({
						json: {
							...inputData,
							_agent: {
								decision: 'decided',
								chosen_action: decision.chosen_action,
								reason: decision.reason,
								risk_level: decision.risk_level,
							},
						},
					});
				} else if (decision.output === 'needs_approval') {
					// AI minta approval — polling sampai user merespons atau timeout
					const approvalId = decision.approval_id!;
					const startTime = Date.now();
					const timeoutMs = approvalTimeoutSeconds * 1000;
					let approvalStatus = 'pending';
					let finalDecision: IDataObject = {};

					// Poll status approval setiap 5 detik
					while (Date.now() - startTime < timeoutMs) {
						await new Promise((resolve) => setTimeout(resolve, 5000));

						const statusResponse = await fetch(`${agentServiceUrl}/approval/${approvalId}`);
						if (statusResponse.ok) {
							const statusData = (await statusResponse.json()) as {
								status: string;
								response_note?: string;
							};
							approvalStatus = statusData.status;

							if (approvalStatus !== 'pending') {
								finalDecision = statusData as IDataObject;
								break;
							}
						}
					}

					// Tandai expired jika timeout habis tanpa respons
					if (approvalStatus === 'pending') {
						approvalStatus = 'expired';
					}

					const approvalOutput: INodeExecutionData = {
						json: {
							...inputData,
							_agent: {
								decision: 'needs_approval',
								approval_id: approvalId,
								approval_status: approvalStatus,
								chosen_action: decision.chosen_action,
								reason: decision.reason,
								risk_level: decision.risk_level,
								...finalDecision,
							},
						},
					};

					needsApprovalItems.push(approvalOutput);
				} else {
					// AI tidak bisa memutuskan — kirim ke output error
					errorItems.push({
						json: {
							...inputData,
							_agent: {
								decision: 'error',
								reason: decision.reason,
								risk_level: decision.risk_level,
								error: decision.error,
							},
						},
					});
				}
			} catch (error) {
				// Error teknis (network, timeout, dll)
				if (this.continueOnFail()) {
					errorItems.push({
						json: {
							...inputData,
							_agent: {
								decision: 'error',
								reason: 'Error teknis saat menghubungi Agent Service',
								error: error instanceof Error ? error.message : String(error),
							},
						},
					});
				} else {
					throw error;
				}
			}
		}

		return [decidedItems, needsApprovalItems, errorItems];
	}
}
