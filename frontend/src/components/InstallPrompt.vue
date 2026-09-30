<template>
	<!-- Installing the app: Android and desktop browsers install it in one tap; Safari on
	     iPhone needs the steps. Offered once on a phone, then from the profile and login. -->
	<ion-modal :is-open="install.open" :initial-breakpoint="1" :breakpoints="[0, 1]" class="ms-sheet" @didDismiss="dismiss">
		<div class="bg-white px-5 pb-[max(24px,env(safe-area-inset-bottom))] pt-6">
			<div class="flex items-center gap-3.5">
				<img :src="brand.icon" alt="" class="h-16 w-16 shrink-0 rounded-[18px] object-contain shadow-[0_8px_18px_rgba(var(--ms-shadow-rgb,14,59,46),0.25)]" />
				<div>
					<h2 class="text-[20px] font-bold text-brand-ink">{{ __("Install {0} on your phone", [brand.app_title]) }}</h2>
					<p class="ms-caption">{{ __("The employee app · free, no app store needed") }}</p>
				</div>
			</div>

			<ul class="mt-[18px] flex flex-col gap-2.5">
				<li v-for="benefit in benefits" :key="benefit" class="flex items-center gap-2.5 text-[14.5px] text-brand-ink">
					<span class="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-state-success/[.12] text-state-success-text">
						<AppIcon name="check" :size="15" :stroke-width="2.4" />
					</span>
					{{ benefit }}
				</li>
			</ul>

			<Segmented
				v-model="platform"
				class="mt-5"
				:options="[
					{ value: 'ios', label: __('iPhone') },
					{ value: 'android', label: __('Android') },
				]"
			/>

			<ol class="mt-4 flex flex-col gap-2.5">
				<li
					v-for="(step, index) in steps"
					:key="index"
					class="flex items-center gap-3 rounded-2xl border border-brand-roots/[.08] bg-brand-sand/50 px-3 py-2.5"
				>
					<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-roots text-[13px] font-bold text-brand-sand">
						{{ index + 1 }}
					</span>
					<span class="grow text-[14.5px] text-brand-ink">{{ step.text }}</span>
					<span v-if="step.icon" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-brand-roots/[.12] bg-white text-brand-roots">
						<AppIcon :name="step.icon" :size="20" />
					</span>
				</li>
			</ol>

			<div class="mt-[18px] flex gap-2.5">
				<button v-if="platform === 'android' && install.prompt" type="button" class="ms-primary-button grow" @click="installNow">
					<AppIcon name="download" :size="20" />
					{{ __("Install now") }}
				</button>
				<button v-else type="button" class="ms-primary-button grow" @click="install.open = false">{{ __("Done") }}</button>
				<button type="button" class="h-14 w-[110px] shrink-0 rounded-[18px] bg-brand-sand text-[15px] font-semibold text-brand-roots" @click="install.open = false">
					{{ __("Later") }}
				</button>
			</div>
		</div>
	</ion-modal>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from "vue"
import { IonModal } from "@ionic/vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import Segmented from "@/components/ui/Segmented.vue"
import { brand } from "@/data/brand"
import { install } from "@/data/ui"

const __ = inject("$translate")

const platform = ref(install.platform)
const benefits = [__("Opens full screen, like any app"), __("Instant notifications for approvals and salary"), __("Faster to open than the browser")]

const steps = computed(() =>
	platform.value === "ios"
		? [
				{ text: __("Tap the Share button in Safari"), icon: "share" },
				{ text: __("Choose “Add to Home Screen”"), icon: "plus-square" },
				{ text: __("Tap “Add” and it appears as {0}", [brand.app_title]) },
		  ]
		: [
				{ text: __("Open the browser menu"), icon: "more" },
				{ text: __("Choose “Install app” or “Add to Home screen”"), icon: "plus-square" },
				{ text: __("Confirm, and it appears as {0}", [brand.app_title]) },
		  ]
)

async function installNow() {
	const prompt = install.prompt
	install.open = false
	if (!prompt) return
	prompt.prompt()
	await prompt.userChoice
	install.prompt = null
}

// Offered by itself once every two weeks, on phones only (wide screens show the install
// button beside the app).
const DISMISSED = "ms_hrms:install_dismissed"
const recentlyDismissed = () => {
	try {
		return Date.now() - Number(localStorage.getItem(DISMISSED) || 0) < 14 * 24 * 3600 * 1000
	} catch {
		return true
	}
}
const onPhone = () => window.matchMedia("(max-width: 767px)").matches
const offer = () => {
	if (!install.standalone && onPhone() && !recentlyDismissed()) install.open = true
}

function dismiss() {
	install.open = false
	try {
		localStorage.setItem(DISMISSED, String(Date.now()))
	} catch {
		// private browsing
	}
}

onMounted(() => {
	if (install.platform === "ios") setTimeout(offer, 4000)
})
watch(
	() => install.prompt,
	(prompt) => prompt && offer()
)
</script>
