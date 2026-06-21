<script setup lang="ts">
import { N8nButton, N8nHeading } from '@n8n/design-system';
import { useI18n } from '@n8n/i18n';
import { computed } from 'vue';
import { useUsersStore } from '@/features/settings/users/users.store';
import mstLogo from '@/app/mst-logo.svg?url';

defineProps<{
	showWelcomeScreen: boolean;
}>();

const emit = defineEmits<{
	startNewChat: [];
}>();

const usersStore = useUsersStore();
const i18n = useI18n();

const currentUserName = computed(() => {
	const user = usersStore.currentUser;
	if (!user) return '';
	const full = [user.firstName, user.lastName].filter(Boolean).join(' ');
	return full || user.email || '';
});

function handleStartNewChat() {
	emit('startNewChat');
}
</script>

<template>
	<Transition name="welcome-fade" mode="out-in">
		<div v-if="showWelcomeScreen" key="welcome" :class="$style.welcomeContent">
			<img :src="mstLogo" alt="MST Logo" :class="$style.mstLogo" />

			<div :class="$style.header">
				<N8nHeading tag="h2" bold size="xlarge">
					Selamat datang<span v-if="currentUserName">, {{ currentUserName }}</span
					>!
				</N8nHeading>
			</div>

			<N8nButton
				variant="solid"
				size="medium"
				icon="plus"
				data-test-id="welcome-start-new-chat"
				@click="handleStartNewChat"
			>
				{{ i18n.baseText('chatHub.welcome.button.startNewChat') }}
			</N8nButton>
		</div>
	</Transition>
</template>

<style lang="scss" module>
.welcomeContent {
	position: absolute;
	left: 0;
	top: 0;
	width: 100%;
	height: 100%;
	z-index: 100;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: var(--spacing--xl);
	background-color: var(--color--background--light-2);
}

.mstLogo {
	height: 72px;
	width: auto;
	object-fit: contain;
}

.header {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
}
</style>

<style lang="scss">
.welcome-fade-enter-active,
.welcome-fade-leave-active {
	transition: opacity 0.2s ease;
}

.welcome-fade-enter-from,
.welcome-fade-leave-to {
	opacity: 0;
}
</style>
