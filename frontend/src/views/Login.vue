<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div v-if="resetPassword.showDialog" class="flex min-h-full flex-col bg-white">
				<header class="flex items-center justify-between px-6 pb-4 pt-[max(16px,env(safe-area-inset-top))]">
					<div class="text-lg font-semibold text-brand-ink">{{ __("Reset Password") }}</div>
					<button type="button" class="ms-link" @click="resetPassword.showDialog = false">{{ __("Back to Login") }}</button>
				</header>
				<div class="flex flex-1 flex-col items-center justify-center px-8 text-center">
					<p class="text-brand-ink/80">{{ __("Your password has expired. Please reset your password to continue") }}</p>
					<a class="ms-primary-button mt-6 px-6" :href="resetPassword.link" target="_blank">{{ __("Go to Reset Password page") }}</a>
				</div>
			</div>

			<!-- ms-login* classes are also hooks for themes (ms_hrms_pwa_include_css). -->
			<div v-else class="ms-login flex min-h-full flex-col">
				<header class="ms-login-brand relative overflow-hidden rounded-b-[36px] bg-brand-roots px-6 pb-20 pt-[max(28px,env(safe-area-inset-top))] text-brand-sand">
					<svg aria-hidden="true" width="220" height="260" viewBox="0 0 220 260" fill="none" class="absolute -left-10 -top-2.5 opacity-[.09]">
						<g stroke="currentColor" stroke-width="12" stroke-linecap="round" class="text-brand-mint">
							<path d="M40 0v120M104 0v180M168 0v90" />
						</g>
						<g fill="currentColor" class="text-brand-mint">
							<circle cx="40" cy="146" r="20" />
							<circle cx="104" cy="206" r="20" />
							<circle cx="168" cy="116" r="20" />
						</g>
					</svg>
					<div class="relative flex items-center justify-between gap-3">
						<img v-if="brand.logo && brand.dark_header" :src="brand.logo" :alt="brand.app_title" class="ms-login-logo h-[34px] w-auto max-w-[60vw] object-contain" />
						<img v-else :src="brand.icon" :alt="brand.app_title" class="ms-login-icon h-11 w-11 rounded-xl object-contain" />
						<button
							v-if="otherLanguage"
							type="button"
							class="ms-login-languages inline-flex h-10 items-center gap-1.5 rounded-full border border-brand-sand/[.22] px-3.5 text-[13.5px] font-semibold"
							@click="switchLanguage(otherLanguage.value)"
						>
							<AppIcon name="globe" :size="16" />
							{{ otherLanguage.label }}
						</button>
					</div>
					<h1 class="ms-login-title relative mt-11 text-[30px] font-bold leading-snug">{{ __("Welcome to {0}", [brand.app_title]) }}</h1>
					<p class="relative mt-2 text-[15.5px] leading-7 text-brand-sand/70">{{ __("Your attendance, requests and salary in one place.") }}</p>
				</header>

				<main class="relative mx-4 -mt-14 rounded-[28px] bg-white px-5 py-6 shadow-[0_18px_40px_rgba(var(--ms-shadow-rgb,14,59,46),0.10)]">
					<h2 class="text-[20px] font-bold text-brand-ink">{{ __("Login") }}</h2>

					<form v-if="!user_pass_login_disabled.data" class="mt-[18px] flex flex-col gap-3.5" @submit.prevent="submit">
						<label class="block">
							<span class="mb-1.5 block text-[13.5px] font-semibold text-brand-ink/80">{{ __("Email") }}</span>
							<span class="relative block">
								<input
									v-model="email"
									type="text"
									dir="ltr"
									autocomplete="username"
									:placeholder="__('johndoe@mail.com')"
									class="h-[52px] w-full rounded-2xl border-[1.5px] border-brand-roots/[.12] bg-brand-sand/40 px-11 text-[15px] text-brand-ink focus:border-brand-emerald focus:ring-4 focus:ring-brand-emerald/[.12]"
								/>
								<AppIcon name="mail" :size="20" class="pointer-events-none absolute start-3.5 top-4 text-brand-muted" />
							</span>
						</label>
						<label class="block">
							<span class="mb-1.5 block text-[13.5px] font-semibold text-brand-ink/80">{{ __("Password") }}</span>
							<span class="relative block">
								<input
									v-model="password"
									:type="showPassword ? 'text' : 'password'"
									autocomplete="current-password"
									placeholder="••••••"
									class="h-[52px] w-full rounded-2xl border-[1.5px] border-brand-roots/[.12] bg-brand-sand/40 pe-12 ps-11 text-[15px] text-brand-ink focus:border-brand-emerald focus:ring-4 focus:ring-brand-emerald/[.12]"
								/>
								<AppIcon name="lock" :size="20" class="pointer-events-none absolute start-3.5 top-4 text-brand-muted" />
								<button
									type="button"
									class="absolute end-1 top-1 flex h-11 w-11 items-center justify-center text-brand-muted"
									:aria-label="showPassword ? __('Hide password') : __('Show password')"
									@click="showPassword = !showPassword"
								>
									<AppIcon :name="showPassword ? 'eye-off' : 'eye'" :size="20" />
								</button>
							</span>
						</label>

						<ErrorMessage :message="errorMessage" />

						<div class="flex justify-end">
							<router-link :to="{ name: 'ForgotPassword', query: email ? { email } : {} }" class="ms-link">
								{{ __("Forgot Password?") }}
							</router-link>
						</div>

						<button type="submit" class="ms-primary-button" :disabled="session.login.loading">
							{{ session.login.loading ? __("Logging in...") : __("Login") }}
						</button>
					</form>

					<template v-if="authProviders.data?.length">
						<div v-if="!user_pass_login_disabled.data" class="ms-caption my-4 text-center">{{ __("or") }}</div>
						<div class="flex flex-col gap-2.5">
							<a v-for="provider in authProviders.data" :key="provider.name" class="ms-secondary-button" :href="provider.auth_url">
								<img class="h-4 w-4" :src="provider.icon" :alt="provider.provider_name" />
								<span>{{ __("Login with {0}", [provider.provider_name]) }}</span>
							</a>
						</div>
					</template>

					<div v-else-if="user_pass_login_disabled.data" class="ms-caption py-8 text-center">
						{{ __("No login methods are available. Please contact your administrator.") }}
					</div>
				</main>

				<button
					v-if="!install.standalone"
					type="button"
					class="mx-4 mt-5 flex items-center gap-3 rounded-[20px] border-[1.5px] border-dashed border-brand-roots/[.18] px-3.5 py-3 text-start"
					@click="install.open = true"
				>
					<img :src="brand.icon" alt="" class="h-10 w-10 shrink-0 rounded-xl object-contain" />
					<span class="grow">
						<span class="block text-[14.5px] font-semibold text-brand-ink">{{ __("Install the app on your phone") }}</span>
						<span class="block text-[12.5px] text-brand-muted">{{ __("Opens full screen, like any app") }}</span>
					</span>
					<AppIcon name="forward" :size="20" class="text-brand-muted" />
				</button>
				<div class="h-8" />
			</div>

			<Dialog v-model="otp.showDialog">
				<template #body-title>
					<h2 class="text-lg font-bold">{{ __("OTP Verification") }}</h2>
				</template>
				<template #body-content>
					<p class="mb-4" v-if="otp.verification.prompt">
						{{ otp.verification.prompt }}
					</p>

					<form class="flex flex-col space-y-4" @submit.prevent="submit">
						<Input :label="__('OTP Code')" type="text" placeholder="000000" v-model="otp.code" autocomplete="one-time-code" />
						<ErrorMessage :message="errorMessage" />
						<Button :loading="session.otp.loading" variant="solid" class="!mt-6 disabled:bg-gray-700 disabled:text-white">
							{{ __("Verify") }}
						</Button>
					</form>
				</template>
			</Dialog>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { computed, inject, reactive, ref } from "vue"
import { Input, Button, ErrorMessage, Dialog, createResource } from "frappe-ui"

import AppIcon from "@/components/ui/AppIcon.vue"
import { brand, languages } from "@/data/brand"
import { install } from "@/data/ui"

const currentLanguage = window.frappe?.boot?.lang
const otherLanguage = computed(() => languages.find((language) => language.value !== currentLanguage))

// Before signing in the language is a cookie; afterwards it is the user's own.
function switchLanguage(language) {
	if (language === currentLanguage) return
	document.cookie = `preferred_language=${language}; path=/; max-age=31536000; SameSite=Lax`
	window.location.reload()
}

const email = ref(null)
const password = ref(null)
const showPassword = ref(false)
const errorMessage = ref("")

const resetPassword = reactive({
	showDialog: false,
	link: "",
})
const otp = reactive({
	showDialog: false,
	tmp_id: "",
	code: "",
	verification: {},
})

const session = inject("$session")
const __ = inject("$translate")

async function submit(e) {
	try {
		let response
		if (otp.showDialog) {
			response = await session.otp(otp.tmp_id, otp.code)
		} else {
			response = await session.login(email.value, password.value)
		}

		if (response.message === "Password Reset") {
			resetPassword.showDialog = true
			resetPassword.link = response.redirect_to
		} else {
			resetPassword.showDialog = false
			resetPassword.link = ""
		}

		// OTP verification
		if (response.verification) {
			if (response.verification.setup) {
				otp.showDialog = true
				otp.tmp_id = response.tmp_id
				otp.verification = response.verification
			} else {
				// Don't bother handling impossible OTP setup (e.g. no phone number).
				window.open("/login?redirect-to=" + encodeURIComponent(window.location.pathname), "_blank")
			}
		}
	} catch (error) {
		errorMessage.value = error.messages.join("\n")
	}
}

const user_pass_login_disabled = createResource({
	url: "hrms.api.system_settings.get_user_pass_login_disabled",
	method: "GET",
	initialData: 1,
	auto: true,
})

const authProviders = createResource({
	url: "hrms.api.oauth.oauth_providers",
	auto: true,
})
</script>
