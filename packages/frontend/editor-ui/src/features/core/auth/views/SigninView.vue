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
					viewBox="0 0 175 95"
					xmlns="http://www.w3.org/2000/svg"
					aria-label="MST Logo"
				>
					<defs>
						<linearGradient
							id="mstGrad"
							x1="0"
							y1="95"
							x2="175"
							y2="0"
							gradientUnits="userSpaceOnUse"
						>
							<stop offset="0%" stop-color="#14C2DA" />
							<stop offset="42%" stop-color="#7ABF3E" />
							<stop offset="100%" stop-color="#E8A020" />
						</linearGradient>
					</defs>
					<g
						fill="none"
						stroke="url(#mstGrad)"
						stroke-width="15"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<!-- m: left pillar -->
						<line x1="12" y1="80" x2="12" y2="40" />
						<!-- m: left arch -->
						<path d="M12,40 Q12,16 37,16 Q62,16 62,40" />
						<!-- m: middle pillar -->
						<line x1="62" y1="80" x2="62" y2="40" />
						<!-- m: right arch -->
						<path d="M62,40 Q62,16 87,16 Q112,16 112,40" />
						<!-- m: right pillar -->
						<line x1="112" y1="80" x2="112" y2="40" />
						<!-- +: vertical -->
						<line x1="150" y1="6" x2="150" y2="80" />
						<!-- +: horizontal -->
						<line x1="128" y1="43" x2="172" y2="43" />
					</g>
				</svg>
				<div :class="$style.logoText">mitra <strong>solusi</strong> telematika</div>
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
				<span :class="$style.footerBrand">EnterpriseSecure</span>
				<span :class="$style.footerCopy">© 2024 Enterprise Corp. All rights reserved.</span>
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
	background: #ffffff;
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
	width: 100px;
	height: auto;
}

.logoText {
	margin-top: 6px;
	font-size: 13px;
	color: #1e3a56;
	letter-spacing: 0.3px;

	strong {
		font-weight: 700;
	}
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
		background: #ffffff;
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
	color: #ffffff;
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
	border-top-color: #ffffff;
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
