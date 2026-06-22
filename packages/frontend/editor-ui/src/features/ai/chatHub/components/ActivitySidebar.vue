<script setup lang="ts">
/**
 * ActivitySidebar
 *
 * Ditampilkan di sidebar kiri Chat Hub, di bawah menu "New Chat / Personal Agents / Workflow Agents".
 * Menampilkan:
 *   1. Workflow terakhir yang dibuat user via chat
 *   2. Approval yang masih pending (dengan tombol Setuju / Tolak)
 *
 * Data diambil dari Agent Service (mst-agent-service:8000).
 */

import { onMounted, watch } from 'vue';
import { N8nText, N8nButton } from '@n8n/design-system';
import { useActivityStore } from '@/features/ai/chatHub/activity.store';
import { useUsersStore } from '@/features/settings/users/users.store';

defineProps<{ isCollapsed: boolean }>();

const activityStore = useActivityStore();
const usersStore = useUsersStore();

// Label singkat untuk tingkat risiko
function riskLabel(level: string): string {
	const labels: Record<string, string> = {
		low: 'Rendah',
		medium: 'Sedang',
		high: 'Tinggi',
		critical: 'Kritis',
	};
	return labels[level] ?? level;
}

// Warna chip risiko
function riskColor(level: string): string {
	const colors: Record<string, string> = {
		low: 'var(--color-success)',
		medium: 'var(--color-warning)',
		high: 'var(--color-danger)',
		critical: 'var(--color-danger)',
	};
	return colors[level] ?? 'var(--color-text-light)';
}

// Format tanggal singkat: "22 Jun" atau "Hari ini"
function formatDate(isoString: string): string {
	const date = new Date(isoString);
	const now = new Date();
	const isToday =
		date.getDate() === now.getDate() &&
		date.getMonth() === now.getMonth() &&
		date.getFullYear() === now.getFullYear();

	if (isToday) {
		return `Hari ini ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
	}

	return date.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

async function handleApprove(approvalId: string): Promise<void> {
	await activityStore.respondApproval(approvalId, 'approved');
}

async function handleReject(approvalId: string): Promise<void> {
	await activityStore.respondApproval(approvalId, 'rejected');
}

onMounted(() => {
	const userId = usersStore.currentUserId;
	if (userId) {
		void activityStore.fetchActivity(userId);
	}
});

// Re-fetch ketika user ID berubah (misalnya setelah login)
watch(
	() => usersStore.currentUserId,
	(newId) => {
		if (newId) void activityStore.fetchActivity(newId);
	},
);
</script>

<template>
	<div v-if="!isCollapsed && activityStore.hasActivity" :class="$style.container">
		<div :class="$style.divider" />

		<!-- ===== APPROVAL PENDING ===== -->
		<div v-if="activityStore.hasPendingApprovals" :class="$style.section">
			<N8nText :class="$style.sectionTitle" size="small" bold color="text-light">
				Menunggu Persetujuan
			</N8nText>

			<div
				v-for="approval in activityStore.pendingApprovals"
				:key="approval.id"
				:class="$style.approvalCard"
			>
				<!-- Nama node + chip risiko -->
				<div :class="$style.approvalHeader">
					<N8nText size="small" bold>{{ approval.node_name }}</N8nText>
					<span
						:class="$style.riskChip"
						:style="{ backgroundColor: riskColor(approval.risk_level) }"
					>
						{{ riskLabel(approval.risk_level) }}
					</span>
				</div>

				<!-- Deskripsi aksi yang diminta AI -->
				<N8nText size="xsmall" color="text-light" :class="$style.approvalDesc">
					{{ approval.action_description }}
				</N8nText>

				<!-- Tombol approve / reject -->
				<div :class="$style.approvalButtons">
					<N8nButton size="mini" type="success" @click="handleApprove(approval.id)">
						Setuju
					</N8nButton>
					<N8nButton size="mini" type="danger" @click="handleReject(approval.id)">
						Tolak
					</N8nButton>
				</div>
			</div>
		</div>

		<!-- ===== WORKFLOW TERAKHIR ===== -->
		<div v-if="activityStore.recentWorkflows.length > 0" :class="$style.section">
			<N8nText :class="$style.sectionTitle" size="small" bold color="text-light">
				Workflow Terakhir
			</N8nText>

			<a
				v-for="wf in activityStore.recentWorkflows"
				:key="wf.workflow_id"
				:href="wf.workflow_url"
				target="_blank"
				:class="$style.workflowItem"
			>
				<!-- Icon workflow -->
				<span :class="$style.workflowIcon">⚡</span>

				<div :class="$style.workflowInfo">
					<N8nText size="small" :class="$style.workflowName">
						{{ wf.workflow_name }}
					</N8nText>
					<N8nText size="xsmall" color="text-light">
						{{ wf.step_count }} langkah · {{ formatDate(wf.created_at) }}
					</N8nText>
				</div>
			</a>
		</div>
	</div>
</template>

<style lang="scss" module>
.container {
	display: flex;
	flex-direction: column;
	gap: var(--spacing--2xs);
}

.divider {
	height: 1px;
	background-color: var(--color-foreground-base);
	margin: 0 var(--spacing--3xs);
}

.section {
	display: flex;
	flex-direction: column;
	gap: 2px;
	padding: var(--spacing--2xs) var(--spacing--3xs) 0;
}

.sectionTitle {
	padding: 0 var(--spacing--4xs) var(--spacing--3xs) var(--spacing--4xs);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	font-size: 10px;
}

/* ===== APPROVAL CARD ===== */
.approvalCard {
	background-color: var(--color-foreground-base);
	border-radius: var(--border-radius-base);
	padding: var(--spacing--3xs) var(--spacing--2xs);
	margin-bottom: var(--spacing--3xs);
	display: flex;
	flex-direction: column;
	gap: var(--spacing--4xs);
}

.approvalHeader {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: var(--spacing--3xs);
}

.riskChip {
	font-size: 9px;
	font-weight: 600;
	color: white;
	padding: 1px 6px;
	border-radius: 10px;
	white-space: nowrap;
}

.approvalDesc {
	line-height: 1.4;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.approvalButtons {
	display: flex;
	gap: var(--spacing--4xs);
	margin-top: var(--spacing--4xs);
}

/* ===== WORKFLOW ITEM ===== */
.workflowItem {
	display: flex;
	align-items: center;
	gap: var(--spacing--3xs);
	padding: var(--spacing--3xs) var(--spacing--4xs);
	border-radius: var(--border-radius-base);
	text-decoration: none;
	color: inherit;
	cursor: pointer;

	&:hover {
		background-color: var(--color-foreground-base);
	}
}

.workflowIcon {
	font-size: 14px;
	flex-shrink: 0;
}

.workflowInfo {
	display: flex;
	flex-direction: column;
	gap: 1px;
	min-width: 0; // agar text-overflow bekerja
}

.workflowName {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
</style>
