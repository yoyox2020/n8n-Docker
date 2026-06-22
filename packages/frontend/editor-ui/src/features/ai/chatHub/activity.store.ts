/**
 * Activity Store
 *
 * Menyimpan dan me-refresh "aktivitas terakhir" user dari Agent Service:
 * - Workflow yang baru-baru ini dibuat via chat
 * - Approval yang masih menunggu keputusan user
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

// ===== TIPE =====

interface RecentWorkflow {
	id: number;
	workflow_id: string;
	workflow_name: string;
	workflow_url: string;
	step_count: number;
	original_prompt: string;
	created_at: string;
}

interface PendingApproval {
	id: string;
	node_name: string;
	action_description: string;
	risk_level: string;
	requested_at: string;
}

// ===== STORE =====

export const useActivityStore = defineStore('mst-activity', () => {
	// State
	const recentWorkflows = ref<RecentWorkflow[]>([]);
	const pendingApprovals = ref<PendingApproval[]>([]);
	const loading = ref(false);
	const lastFetchedUserId = ref<string | null>(null);

	// Computed
	const hasPendingApprovals = computed(() => pendingApprovals.value.length > 0);
	const hasActivity = computed(
		() => recentWorkflows.value.length > 0 || pendingApprovals.value.length > 0,
	);

	// Ambil URL Agent Service — sama dengan yang dipakai backend, tapi via window._env atau fallback
	function getAgentServiceUrl(): string {
		// Di production Docker, agent service ada di port yang di-expose atau via proxy
		// Default ke localhost:8000 untuk development lokal
		return (
			(window as unknown as Record<string, string>).__AGENT_SERVICE_URL__ ?? 'http://localhost:8000'
		);
	}

	// Fetch aktivitas terakhir dari Agent Service
	async function fetchActivity(userId: string): Promise<void> {
		if (!userId) return;

		loading.value = true;
		lastFetchedUserId.value = userId;

		try {
			const url = `${getAgentServiceUrl()}/memory/${userId}/last-activity?limit=5`;
			const response = await fetch(url, { signal: AbortSignal.timeout(8_000) });

			if (!response.ok) return;

			const data = (await response.json()) as {
				recent_workflows: RecentWorkflow[];
				pending_approvals: PendingApproval[];
			};

			recentWorkflows.value = data.recent_workflows ?? [];
			pendingApprovals.value = data.pending_approvals ?? [];
		} catch {
			// Agent Service mungkin belum running — tidak perlu error ke user
		} finally {
			loading.value = false;
		}
	}

	// Respond approval (approve / reject) dan refresh
	async function respondApproval(
		approvalId: string,
		decision: 'approved' | 'rejected',
		note?: string,
	): Promise<void> {
		const url = `${getAgentServiceUrl()}/approval/${approvalId}/respond`;

		await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ decision, note }),
			signal: AbortSignal.timeout(10_000),
		});

		// Hapus dari local list langsung tanpa tunggu re-fetch
		pendingApprovals.value = pendingApprovals.value.filter((a) => a.id !== approvalId);
	}

	return {
		recentWorkflows,
		pendingApprovals,
		loading,
		hasPendingApprovals,
		hasActivity,
		fetchActivity,
		respondApproval,
	};
});
