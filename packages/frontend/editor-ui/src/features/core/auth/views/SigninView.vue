<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import MfaView from './MfaView.vue';

import { useToast } from '@/app/composables/useToast';
import { useI18n } from '@n8n/i18n';
import { useTelemetry } from '@/app/composables/useTelemetry';

import { useUsersStore } from '@/features/settings/users/users.store';
import { useSettingsStore } from '@/app/stores/settings.store';

import { MFA_AUTHENTICATION_REQUIRED_ERROR_CODE, VIEWS, MFA_FORM } from '@/app/constants';
import type { LoginRequestDto } from '@n8n/api-types';

export type EmailOrLdapLoginIdAndPassword = Pick<
	LoginRequestDto,
	'emailOrLdapLoginId' | 'password'
>;

export type MfaCodeOrMfaRecoveryCode = Pick<LoginRequestDto, 'mfaCode' | 'mfaRecoveryCode'>;

const usersStore = useUsersStore();
const settingsStore = useSettingsStore();

const route = useRoute();
const router = useRouter();

const toast = useToast();
const locale = useI18n();
const telemetry = useTelemetry();

const loading = ref(false);
const showMfaView = ref(false);
const emailOrLdapLoginId = ref('');
const password = ref('');
const reportError = ref(false);

// Local form state for custom template
const localEmail = ref('');
const localPassword = ref('');
const showPassword = ref(false);

const onMFASubmitted = async (form: MfaCodeOrMfaRecoveryCode) => {
	await login({
		emailOrLdapLoginId: emailOrLdapLoginId.value,
		password: password.value,
		mfaCode: form.mfaCode,
		mfaRecoveryCode: form.mfaRecoveryCode,
	});
};

const onEmailPasswordSubmitted = async (form: EmailOrLdapLoginIdAndPassword) => {
	await login(form);
};

const isRedirectSafe = () => {
	const redirect = getRedirectQueryParameter();
	if (redirect.startsWith('/')) return true;
	try {
		const url = new URL(redirect);
		return url.origin === window.location.origin;
	} catch {
		return false;
	}
};

const getRedirectQueryParameter = () => {
	let redirect = '';
	if (typeof route.query?.redirect === 'string') {
		redirect = decodeURIComponent(route.query?.redirect);
	}
	return redirect;
};

const login = async (form: LoginRequestDto) => {
	try {
		loading.value = true;
		await usersStore.loginWithCreds({
			emailOrLdapLoginId: form.emailOrLdapLoginId,
			password: form.password,
			mfaCode: form.mfaCode,
			mfaRecoveryCode: form.mfaRecoveryCode,
		});
		loading.value = false;
		await settingsStore.getSettings();

		toast.clearAllStickyNotifications();

		if (settingsStore.isMFAEnforced && !usersStore.currentUser?.mfaAuthenticated) {
			await router.push({ name: VIEWS.PERSONAL_SETTINGS });
			return;
		}

		telemetry.track('User attempted to login', {
			result: showMfaView.value ? 'mfa_success' : 'success',
		});

		if (isRedirectSafe()) {
			const redirect = getRedirectQueryParameter();
			if (redirect.startsWith('http')) {
				window.location.href = redirect;
				return;
			}
			void router.push(redirect);
			return;
		}

		await router.push({ name: VIEWS.HOMEPAGE });
	} catch (error) {
		if (error.errorCode === MFA_AUTHENTICATION_REQUIRED_ERROR_CODE) {
			showMfaView.value = true;
			cacheCredentials(form);
			return;
		}

		telemetry.track('User attempted to login', {
			result: showMfaView.value ? 'mfa_token_rejected' : 'credentials_error',
		});

		if (!showMfaView.value) {
			toast.showError(error, locale.baseText('auth.signin.error'));
			loading.value = false;
			return;
		}

		reportError.value = true;
	}
};

const onBackClick = (fromForm: string) => {
	reportError.value = false;
	if (fromForm === MFA_FORM.MFA_TOKEN) {
		showMfaView.value = false;
		loading.value = false;
	}
};

const onFormChanged = (toForm: string) => {
	if (toForm === MFA_FORM.MFA_RECOVERY_CODE) {
		reportError.value = false;
	}
};

const cacheCredentials = (form: EmailOrLdapLoginIdAndPassword) => {
	emailOrLdapLoginId.value = form.emailOrLdapLoginId;
	password.value = form.password;
};

const handleSubmit = async (e: Event) => {
	e.preventDefault();
	await onEmailPasswordSubmitted({
		emailOrLdapLoginId: localEmail.value,
		password: localPassword.value,
	});
};
</script>

<template>
	<div v-if="showMfaView" :class="$style.mfaWrapper">
		<MfaView
			:report-error="reportError"
			@submit="onMFASubmitted"
			@on-back-click="onBackClick"
			@on-form-changed="onFormChanged"
		/>
	</div>

	<div v-else :class="$style.page">
		<div :class="$style.card">
			<!-- Logo -->
			<div :class="$style.logoSection">
				<svg
					:class="$style.logoSvg"
					viewBox="0 0 142 101"
					xmlns="http://www.w3.org/2000/svg"
					aria-label="MST Logo"
				>
					<path
						d="M0 0 C1.20269531 -0.00257812 2.40539062 -0.00515625 3.64453125 -0.0078125 C7.1875 0.125 7.1875 0.125 10.44921875 0.6953125 C13.26991649 1.35278973 13.26991649 1.35278973 16.1875 0.125 C18.45513574 -0.02148082 20.72782366 -0.0959626 23 -0.125 C24.20269531 -0.15078125 25.40539063 -0.1765625 26.64453125 -0.203125 C31.5461076 0.25082474 34.64584993 1.9006707 38.46484375 4.93359375 C40.59422861 7.64240307 41.08676026 9.82124546 41.75 13.1875 C42.5295278 17.24673821 42.5295278 17.24673821 44.3359375 20.8984375 C47.13600521 22.75333468 49.96503087 23.09301231 53.25 23.6875 C59.97916667 24.91666667 59.97916667 24.91666667 62.1875 27.125 C62.125 29.625 62.125 29.625 61.1875 32.125 C57.23146775 34.25517121 53.80998511 34.33959566 49.375 34.25 C48.21355469 34.23195312 47.05210938 34.21390625 45.85546875 34.1953125 C44.97503906 34.17210937 44.09460938 34.14890625 43.1875 34.125 C42.73375 35.094375 42.28 36.06375 41.8125 37.0625 C40.1875 40.125 40.1875 40.125 38.1875 41.125 C34.13607881 41.38360135 32.64412331 41.42941554 29.1875 39.125 C28.75512695 36.60302734 28.75512695 36.60302734 28.67578125 33.4609375 C28.64033203 32.33945312 28.60488281 31.21796875 28.56835938 30.0625 C28.53452148 28.2990625 28.53452148 28.2990625 28.5 26.5 C28.46583984 25.31664063 28.43167969 24.13328125 28.39648438 22.9140625 C28.31379425 19.9844694 28.24471286 17.0551836 28.1875 14.125 C23.79496227 12.56227811 23.79496227 12.56227811 19.1875 12.125 C19.17291748 12.86137695 19.15833496 13.59775391 19.14331055 14.35644531 C19.06878889 17.69649004 18.97214127 21.03553981 18.875 24.375 C18.85244141 25.53386719 18.82988281 26.69273438 18.80664062 27.88671875 C18.77119141 29.00175781 18.73574219 30.11679687 18.69921875 31.265625 C18.67303467 32.29204102 18.64685059 33.31845703 18.61987305 34.37597656 C18.12888369 37.49768193 17.43630117 38.92068774 15.1875 41.125 C11.625 41.5 11.625 41.5 8.1875 41.125 C5.59418436 38.53168436 5.90069999 37.36080141 5.80859375 33.75 C5.77443359 32.68265625 5.74027344 31.6153125 5.70507812 30.515625 C5.67865234 29.39671875 5.65222656 28.2778125 5.625 27.125 C5.56520913 24.91655442 5.50160015 22.70820786 5.43359375 20.5 C5.40966553 19.51773438 5.3857373 18.53546875 5.36108398 17.5234375 C5.33983481 15.11176734 5.33983481 15.11176734 4.1875 13.125 C0.90335695 12.17432701 -0.50943408 12.02397803 -3.8125 13.125 C-5.09549701 15.69099403 -4.98867702 17.62988286 -5.05859375 20.5 C-5.09146484 21.56734375 -5.12433594 22.6346875 -5.15820312 23.734375 C-5.21939827 25.99468936 -5.27669045 28.25511276 -5.33007812 30.515625 C-5.36423828 31.58296875 -5.39839844 32.6503125 -5.43359375 33.75 C-5.4586499 34.73226562 -5.48370605 35.71453125 -5.50952148 36.7265625 C-5.8125 39.125 -5.8125 39.125 -7.8125 41.125 C-13.99120761 41.68670069 -13.99120761 41.68670069 -16.51025391 39.96386719 C-18.33342501 37.3894156 -18.20062187 35.52755869 -18.2109375 32.390625 C-18.21480469 31.25882813 -18.21867187 30.12703125 -18.22265625 28.9609375 C-18.21105469 27.77757813 -18.19945312 26.59421875 -18.1875 25.375 C-18.19910156 24.20710938 -18.21070313 23.03921875 -18.22265625 21.8359375 C-18.20119085 15.52510889 -18.00372009 10.63710742 -14.8125 5.125 C-10.02578784 0.57762345 -6.46717672 -0.0137746 0 0 Z "
						fill="#378F6D"
						transform="translate(33.8125,20.875)"
					/>
					<path
						d="M0 0 C0.94552734 0.16242187 0.94552734 0.16242187 1.91015625 0.328125 C3.85525625 3.245775 4.36291942 4.95349785 4.91015625 8.328125 C6.02390625 8.43125 7.13765625 8.534375 8.28515625 8.640625 C10.07953125 8.9809375 10.07953125 8.9809375 11.91015625 9.328125 C13.91015625 12.328125 13.91015625 12.328125 13.59765625 14.953125 C12.91015625 17.328125 12.91015625 17.328125 11.91015625 18.328125 C9.58197661 18.69573231 7.24831775 19.03054081 4.91015625 19.328125 C4.89557373 19.88798096 4.88099121 20.44783691 4.8659668 21.0246582 C4.79144273 23.56400637 4.69480044 26.10204578 4.59765625 28.640625 C4.57509766 29.52169922 4.55253906 30.40277344 4.52929688 31.31054688 C4.49384766 32.15810547 4.45839844 33.00566406 4.421875 33.87890625 C4.39569092 34.65919189 4.36950684 35.43947754 4.3425293 36.2434082 C3.80217798 38.84874976 3.04190604 39.76278959 0.91015625 41.328125 C-2.65234375 41.640625 -2.65234375 41.640625 -6.08984375 41.328125 C-9.43543786 37.98253089 -8.44516326 33.36456985 -8.55078125 28.80859375 C-9.1761232 24.77105985 -10.20298277 23.16908183 -13.08984375 20.328125 C-16.90317799 17.81728764 -21.19481559 17.55633298 -25.62890625 16.890625 C-28.08984375 16.328125 -28.08984375 16.328125 -30.08984375 14.328125 C-29.83984375 12.265625 -29.83984375 12.265625 -29.08984375 10.328125 C-25.79024234 8.6783243 -22.09856491 8.94554139 -18.46484375 8.765625 C-17.66304687 8.72244141 -16.86125 8.67925781 -16.03515625 8.63476562 C-14.05359265 8.52861043 -12.07174104 8.42785645 -10.08984375 8.328125 C-9.61546875 7.19375 -9.14109375 6.059375 -8.65234375 4.890625 C-6.35499875 -0.34732161 -5.6237564 0.20412909 0 0 Z "
						fill="#BCA41D"
						transform="translate(114.08984375,20.671875)"
					/>
					<path
						d="M0 0 C4.29 0 8.58 0 13 0 C13 2.31 13 4.62 13 7 C8.71 7 4.42 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#16155D"
						transform="translate(56,76)"
					/>
					<path
						d="M0 0 C0.9075 0.165 1.815 0.33 2.75 0.5 C5.92546075 1.18096091 5.92546075 1.18096091 8.75 0.4375 C9.4925 0.293125 10.235 0.14875 11 0 C11.66 0.66 12.32 1.32 13 2 C12.67 3.65 12.34 5.3 12 7 C7.71 7 3.42 7 -1 7 C-1 1 -1 1 0 0 Z M8 2 C8 2.99 8 3.98 8 5 C8.66 5 9.32 5 10 5 C10 4.01 10 3.02 10 2 C9.34 2 8.68 2 8 2 Z "
						fill="#0F0E58"
						transform="translate(39,76)"
					/>
					<path
						d="M0 0 C0.99 0.495 0.99 0.495 2 1 C2.625 3.0625 2.625 3.0625 3 5 C3.556875 4.814375 4.11375 4.62875 4.6875 4.4375 C7.399133 3.92448835 9.34371039 4.3359276 12 5 C12 6.98 12 8.96 12 11 C8.04 11 4.08 11 0 11 C0 7.37 0 3.74 0 0 Z M5 5 C4.01 6.485 4.01 6.485 3 8 C4.485 8.99 4.485 8.99 6 10 C6.33 9.34 6.66 8.68 7 8 C7.99 7.34 8.98 6.68 10 6 C8.35 5.67 6.7 5.34 5 5 Z M9 8 C8.67 8.66 8.34 9.32 8 10 C8.66 10 9.32 10 10 10 C9.67 9.34 9.34 8.68 9 8 Z "
						fill="#111059"
						transform="translate(125,72)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 0.66 2 1.32 2 2 C4.31 2 6.62 2 9 2 C9.66 3.32 10.32 4.64 11 6 C10.01 6.33 9.02 6.66 8 7 C8.66 7 9.32 7 10 7 C10 7.66 10 8.32 10 9 C6.7 9 3.4 9 0 9 C-1.125 2.25 -1.125 2.25 0 0 Z M2 4 C2 5.32 2 6.64 2 8 C2.66 8 3.32 8 4 8 C4 6.68 4 5.36 4 4 C3.34 4 2.68 4 2 4 Z "
						fill="#13135C"
						transform="translate(77,74)"
					/>
					<path
						d="M0 0 C1.47906892 -0.02689216 2.95827483 -0.04634621 4.4375 -0.0625 C5.26121094 -0.07410156 6.08492187 -0.08570312 6.93359375 -0.09765625 C9 0 9 0 10 1 C10.04080783 2.99958364 10.04254356 5.00045254 10 7 C8.02 7 6.04 7 4 7 C4 5.68 4 4.36 4 3 C3.34 2.67 2.68 2.34 2 2 C2 3.65 2 5.3 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#454580"
						transform="translate(24,76)"
					/>
					<path
						d="M0 0 C1.47906892 -0.02689216 2.95827483 -0.04634621 4.4375 -0.0625 C5.26121094 -0.07410156 6.08492188 -0.08570312 6.93359375 -0.09765625 C9 0 9 0 10 1 C10.04080783 2.99958364 10.04254356 5.00045254 10 7 C9.34 7 8.68 7 8 7 C8 5.35 8 3.7 8 2 C7.34 2 6.68 2 6 2 C6 3.65 6 5.3 6 7 C5.34 7 4.68 7 4 7 C4 5.35 4 3.7 4 2 C3.34 2 2.68 2 2 2 C2 3.65 2 5.3 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#0E0D57"
						transform="translate(99,76)"
					/>
					<path
						d="M0 0 C1.47906892 -0.02689216 2.95827483 -0.04634621 4.4375 -0.0625 C5.26121094 -0.07410156 6.08492187 -0.08570312 6.93359375 -0.09765625 C9 0 9 0 10 1 C10.04080783 2.99958364 10.04254356 5.00045254 10 7 C9.34 7 8.68 7 8 7 C8 5.35 8 3.7 8 2 C7.34 2 6.68 2 6 2 C6 3.65 6 5.3 6 7 C5.34 7 4.68 7 4 7 C4 5.35 4 3.7 4 2 C3.34 2 2.68 2 2 2 C2 3.65 2 5.3 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#0D0D54"
						transform="translate(5,76)"
					/>
					<path
						d="M0 0 C2.625 0.375 2.625 0.375 5 1 C5 1.99 5 2.98 5 4 C4.01 4.495 4.01 4.495 3 5 C3.66 5 4.32 5 5 5 C5 5.66 5 6.32 5 7 C3.02 7 1.04 7 -1 7 C-1.625 4.625 -1.625 4.625 -2 2 C-1.34 1.34 -0.68 0.68 0 0 Z "
						fill="#181763"
						transform="translate(93,76)"
					/>
					<path
						d="M0 0 C1.65 0.33 3.3 0.66 5 1 C5 2.98 5 4.96 5 7 C3.02 7 1.04 7 -1 7 C-0.7525 6.1028125 -0.7525 6.1028125 -0.5 5.1875 C0.1114124 2.88655664 0.1114124 2.88655664 0 0 Z M2 4 C1.67 4.66 1.34 5.32 1 6 C1.66 6 2.32 6 3 6 C2.67 5.34 2.34 4.68 2 4 Z "
						fill="#17175F"
						transform="translate(132,76)"
					/>
					<path
						d="M0 0 C1.65 0.33 3.3 0.66 5 1 C5 2.98 5 4.96 5 7 C3.02 7 1.04 7 -1 7 C-0.67 4.69 -0.34 2.38 0 0 Z M2 4 C1.67 4.66 1.34 5.32 1 6 C1.66 6 2.32 6 3 6 C2.67 5.34 2.34 4.68 2 4 Z "
						fill="#0F0E58"
						transform="translate(111,76)"
					/>
					<path
						d="M0 0 C0.99 0.66 1.98 1.32 3 2 C3.1875 5.625 3.1875 5.625 3 9 C2.01 9 1.02 9 0 9 C-0.66 6.69 -1.32 4.38 -2 2 C-1.34 2 -0.68 2 0 2 C0 1.34 0 0.68 0 0 Z "
						fill="#0D0D5F"
						transform="translate(118,74)"
					/>
					<path
						d="M0 0 C1.485 0.99 1.485 0.99 3 2 C3.1875 5.625 3.1875 5.625 3 9 C2.01 9 1.02 9 0 9 C-1.125 2.25 -1.125 2.25 0 0 Z "
						fill="#13135A"
						transform="translate(20,74)"
					/>
					<path
						d="M0 0 C2.31 0 4.62 0 7 0 C6.67 0.66 6.34 1.32 6 2 C4.68 2 3.36 2 2 2 C2 3.65 2 5.3 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#15145B"
						transform="translate(24,76)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 3.63 2 7.26 2 11 C1.34 11 0.68 11 0 11 C0 7.37 0 3.74 0 0 Z "
						fill="#090950"
						transform="translate(53,72)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 3.3 2 6.6 2 10 C1.34 10 0.68 10 0 10 C-0.19412181 8.52168779 -0.38012131 7.04230684 -0.5625 5.5625 C-0.66691406 4.73878906 -0.77132812 3.91507812 -0.87890625 3.06640625 C-0.91886719 2.38449219 -0.95882812 1.70257813 -1 1 C-0.67 0.67 -0.34 0.34 0 0 Z "
						fill="#0B0B53"
						transform="translate(70,73)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 2.31 2 4.62 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#1A195E"
						transform="translate(16,76)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 2.31 2 4.62 2 7 C1.34 7 0.68 7 0 7 C0 4.69 0 2.38 0 0 Z "
						fill="#070653"
						transform="translate(122,76)"
					/>
					<path
						d="M0 0 C0.33 0 0.66 0 1 0 C1 3.63 1 7.26 1 11 C0.67 11 0.34 11 0 11 C0 7.37 0 3.74 0 0 Z "
						fill="#0C0B52"
						transform="translate(89,72)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 0.66 2 1.32 2 2 C1.34 2 0.68 2 0 2 C0 1.34 0 0.68 0 0 Z "
						fill="#16145D"
						transform="translate(122,73)"
					/>
					<path
						d="M0 0 C0.66 0 1.32 0 2 0 C2 0.66 2 1.32 2 2 C1.34 2 0.68 2 0 2 C0 1.34 0 0.68 0 0 Z "
						fill="#0D0C54"
						transform="translate(16,73)"
					/>
				</svg>
			</div>

			<!-- Heading -->
			<h1 :class="$style.title">Selamat Datang</h1>
			<p :class="$style.subtitle">Silakan masuk ke akun Anda</p>

			<!-- Login form -->
			<form :class="$style.form" @submit="handleSubmit" novalidate>
				<!-- Email -->
				<div :class="$style.fieldGroup">
					<label :class="$style.label" for="mst-email">Email</label>
					<div :class="$style.inputWrapper">
						<span :class="$style.inputIcon">
							<svg
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<path
									d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"
								/>
								<polyline points="22,6 12,13 2,6" />
							</svg>
						</span>
						<input
							id="mst-email"
							v-model="localEmail"
							:class="$style.input"
							type="email"
							placeholder="name@company.com"
							autocomplete="email"
							required
						/>
					</div>
				</div>

				<!-- Password -->
				<div :class="$style.fieldGroup">
					<div :class="$style.labelRow">
						<label :class="$style.label" for="mst-password">Kata Sandi</label>
						<router-link :class="$style.forgotLink" :to="{ name: VIEWS.FORGOT_PASSWORD }">
							Lupa Kata Sandi?
						</router-link>
					</div>
					<div :class="$style.inputWrapper">
						<span :class="$style.inputIcon">
							<svg
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
								<path d="M7 11V7a5 5 0 0 1 10 0v4" />
							</svg>
						</span>
						<input
							id="mst-password"
							v-model="localPassword"
							:class="[$style.input, $style.inputPassword]"
							:type="showPassword ? 'text' : 'password'"
							placeholder="••••••••"
							autocomplete="current-password"
							required
						/>
						<button
							type="button"
							:class="$style.eyeBtn"
							:aria-label="showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'"
							@click="showPassword = !showPassword"
						>
							<svg
								v-if="!showPassword"
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
								<circle cx="12" cy="12" r="3" />
							</svg>
							<svg
								v-else
								width="16"
								height="16"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<path
									d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
								/>
								<line x1="1" y1="1" x2="23" y2="23" />
							</svg>
						</button>
					</div>
				</div>

				<!-- Submit button -->
				<button type="submit" :class="$style.submitBtn" :disabled="loading">
					<span v-if="loading" :class="$style.spinner" />
					<span v-else>Masuk &nbsp;→</span>
				</button>
			</form>

			<!-- Register link -->
			<p :class="$style.registerRow">
				Belum memiliki akun?&nbsp;
				<router-link :class="$style.registerLink" :to="{ name: VIEWS.SIGNUP }">
					Daftar Sekarang
				</router-link>
			</p>
		</div>

		<!-- Footer -->
		<footer :class="$style.footer">
			<div :class="$style.securityBadge">
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				>
					<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
				</svg>
				Keamanan data terjamin oleh MST Protocol
			</div>
			<div :class="$style.footerBottom">
				<span :class="$style.footerBrand">MST</span>
				<span :class="$style.footerCopy">© 2026 MST Corp. All rights reserved.</span>
				<div :class="$style.footerLinks">
					<a href="#">Syarat &amp; Ketentuan</a>
					<span>|</span>
					<a href="#">Kebijakan Privasi</a>
				</div>
			</div>
		</footer>
	</div>
</template>

<style lang="scss" module>
/* ── Page background ─────────────────────────────── */
:global(body) {
	margin: 0;
	padding: 0;
	min-height: 100vh;
	background: linear-gradient(145deg, #daeef7 0%, #c4dff0 60%, #b8d4e9 100%);
}

.page {
	min-height: 100vh;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 24px 16px 0;
	box-sizing: border-box;
}

/* ── Card ────────────────────────────────────────── */
.card {
	background: #fff;
	border-radius: 16px;
	box-shadow: 0 4px 32px rgba(30, 70, 100, 0.12);
	padding: 40px 40px 32px;
	width: 100%;
	max-width: 440px;
	box-sizing: border-box;
}

/* ── Logo ────────────────────────────────────────── */
.logoSection {
	display: flex;
	flex-direction: column;
	align-items: center;
	margin-bottom: 24px;
}

.logoSvg {
	width: 170px;
	height: auto;
}

/* ── Heading ─────────────────────────────────────── */
.title {
	text-align: center;
	font-size: 26px;
	font-weight: 700;
	color: #1a3a50;
	margin: 0 0 6px;
}

.subtitle {
	text-align: center;
	font-size: 14px;
	color: #6b7f90;
	margin: 0 0 28px;
}

/* ── Form ────────────────────────────────────────── */
.form {
	display: flex;
	flex-direction: column;
	gap: 18px;
}

.fieldGroup {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.label {
	font-size: 13px;
	font-weight: 600;
	color: #364e60;
}

.labelRow {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.forgotLink {
	font-size: 13px;
	color: #1a8fa8;
	text-decoration: none;

	&:hover {
		text-decoration: underline;
	}
}

.inputWrapper {
	position: relative;
	display: flex;
	align-items: center;
}

.inputIcon {
	position: absolute;
	left: 12px;
	display: flex;
	align-items: center;
	color: #8fa8bb;
	pointer-events: none;
}

.input {
	width: 100%;
	height: 44px;
	padding: 0 14px 0 40px;
	font-size: 14px;
	color: #1a3a50;
	background: #f7fafc;
	border: 1.5px solid #d0dde6;
	border-radius: 8px;
	box-sizing: border-box;
	outline: none;
	transition:
		border-color 0.18s,
		box-shadow 0.18s;

	&::placeholder {
		color: #a8bcc8;
	}

	&:focus {
		border-color: #1a8fa8;
		box-shadow: 0 0 0 3px rgba(26, 143, 168, 0.12);
		background: #fff;
	}
}

.inputPassword {
	padding-right: 42px;
}

.eyeBtn {
	position: absolute;
	right: 12px;
	background: none;
	border: none;
	padding: 0;
	cursor: pointer;
	display: flex;
	align-items: center;
	color: #8fa8bb;

	&:hover {
		color: #1a8fa8;
	}
}

/* ── Submit button ───────────────────────────────── */
.submitBtn {
	margin-top: 4px;
	width: 100%;
	height: 46px;
	background: #1a3a50;
	color: #fff;
	border: none;
	border-radius: 8px;
	font-size: 15px;
	font-weight: 600;
	cursor: pointer;
	display: flex;
	align-items: center;
	justify-content: center;
	transition:
		background 0.18s,
		transform 0.1s;

	&:hover:not(:disabled) {
		background: #22506e;
	}

	&:active:not(:disabled) {
		transform: scale(0.99);
	}

	&:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	}
}

.spinner {
	width: 18px;
	height: 18px;
	border: 2px solid rgba(255, 255, 255, 0.35);
	border-top-color: #fff;
	border-radius: 50%;
	animation: spin 0.7s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* ── Register link ───────────────────────────────── */
.registerRow {
	text-align: center;
	font-size: 13px;
	color: #6b7f90;
	margin: 20px 0 0;
}

.registerLink {
	color: #1a8fa8;
	text-decoration: none;
	font-weight: 600;

	&:hover {
		text-decoration: underline;
	}
}

/* ── Footer ──────────────────────────────────────── */
.footer {
	width: 100%;
	max-width: 680px;
	margin-top: 24px;
	padding: 0 16px 24px;
	box-sizing: border-box;
}

.securityBadge {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 6px;
	font-size: 12px;
	color: #4a6a7e;
	margin-bottom: 14px;
}

.footerBottom {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding-top: 12px;
	border-top: 1px solid #d0dde6;
	flex-wrap: wrap;
	gap: 8px;
}

.footerBrand {
	font-size: 12px;
	font-weight: 700;
	color: #364e60;
}

.footerCopy {
	font-size: 11px;
	color: #7a96a8;
}

.footerLinks {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 11px;
	color: #7a96a8;

	a {
		color: #4a6a7e;
		text-decoration: none;

		&:hover {
			text-decoration: underline;
		}
	}
}

/* ── MFA wrapper ─────────────────────────────────── */
.mfaWrapper {
	min-height: 100vh;
	display: flex;
	align-items: center;
	justify-content: center;
}
</style>
