<script setup lang="ts">
import { useUIStore } from '@/app/stores/ui.store';
import { useSettingsStore } from '@/app/stores/settings.store';
import { hasPermission } from '@/app/utils/rbac/permissions';
import { EnterpriseEditionFeature } from '@/app/constants';
import { INVITE_USER_MODAL_KEY } from '@/features/settings/users/users.constants';
import { usePageRedirectionHelper } from '@/app/composables/usePageRedirectionHelper';
import { N8nButton, N8nHeading, N8nLink, N8nText, N8nTooltip } from '@n8n/design-system';
import { useI18n } from '@n8n/i18n';
import { computed } from 'vue';
import { I18nT } from 'vue-i18n';
import { ROLE } from '@n8n/api-types';
import { useUsersStore } from '@/features/settings/users/users.store';
import mstLogo from '@/app/mst-logo.svg?url';

defineProps<{
	showWelcomeScreen: boolean;
}>();

const emit = defineEmits<{
	startNewChat: [];
}>();

const uiStore = useUIStore();
const settingsStore = useSettingsStore();
const usersStore = useUsersStore();
const i18n = useI18n();
const { goToUpgrade } = usePageRedirectionHelper();

const currentUserName = computed(() => {
	const user = usersStore.currentUser;
	if (!user) return '';
	const full = [user.firstName, user.lastName].filter(Boolean).join(' ');
	return full || user.email || '';
});

const CHAT_USERS_DOCS_URL = 'https://docs.n8n.io/advanced-ai/chat-hub/#chat-user-role';

const isAdvancedPermissionsEnabled = computed(
	() => settingsStore.isEnterpriseFeatureEnabled[EnterpriseEditionFeature.AdvancedPermissions],
);

const hasInvitePermission = computed(() =>
	hasPermission(['rbac'], { rbac: { scope: 'user:create' } }),
);

const showInviteButton = computed(() => hasInvitePermission.value);
const isInviteDisabled = computed(() => !isAdvancedPermissionsEnabled.value);

function handleStartNewChat() {
	emit('startNewChat');
}

function handleInviteUsers() {
	uiStore.openModalWithData({ name: INVITE_USER_MODAL_KEY, data: { initialRole: ROLE.ChatUser } });
}

function handleUpgradeClick() {
	void goToUpgrade('chat-hub', 'upgrade-advanced-permissions');
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
				<N8nText size="large" color="text-light">
					{{ i18n.baseText('chatHub.welcome.subtitle') }}
				</N8nText>
			</div>

			<div :class="$style.buttonGroup">
				<N8nButton
					variant="solid"
					size="medium"
					icon="plus"
					data-test-id="welcome-start-new-chat"
					@click="handleStartNewChat"
				>
					{{ i18n.baseText('chatHub.welcome.button.startNewChat') }}
				</N8nButton>

				<N8nTooltip v-if="showInviteButton" :disabled="!isInviteDisabled">
					<template #content>
						<I18nT keypath="chatHub.welcome.inviteUpgrade.tooltip" scope="global">
							<template #link>
								<N8nLink size="small" @click="handleUpgradeClick">
									{{ i18n.baseText('generic.upgrade') }}
								</N8nLink>
							</template>
							<template #docsLink>
								<N8nLink size="small" :href="CHAT_USERS_DOCS_URL" target="_blank" rel="noopener">
									{{ i18n.baseText('chatHub.welcome.inviteUpgrade.here') }}
								</N8nLink>
							</template>
						</I18nT>
					</template>
					<N8nButton
						variant="subtle"
						size="medium"
						icon="users"
						:disabled="isInviteDisabled"
						data-test-id="welcome-invite-chat-users"
						@click="handleInviteUsers"
					>
						{{ i18n.baseText('chatHub.welcome.button.inviteChatUsers') }}
					</N8nButton>
				</N8nTooltip>
			</div>
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
	gap: var(--spacing--xs);
}

.buttonGroup {
	display: flex;
	gap: var(--spacing--sm);
	justify-content: center;
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
