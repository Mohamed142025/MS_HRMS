<template>
	<!-- On a wide screen the app stays phone-sized, in a frame, with this panel beside it:
	     what the app is, a QR code to open it on a phone, and the install button. -->
	<Teleport to="body">
		<aside class="ms-desktop-panel" :aria-label="brand.app_title">
			<div class="flex items-center justify-between">
				<span class="inline-flex items-center rounded-2xl bg-brand-roots px-4 py-2.5">
					<img v-if="brand.logo && brand.dark_header" :src="brand.logo" :alt="brand.app_title" class="h-8 w-auto max-w-[240px] object-contain" />
					<span v-else class="text-lg font-bold text-brand-sand">{{ brand.app_title }}</span>
				</span>
			</div>

			<div class="flex grow flex-col justify-center">
				<span class="self-start rounded-full border border-brand-roots/[.12] bg-white px-3.5 py-1.5 text-sm font-semibold text-brand-emerald">
					{{ __("The employee app") }}
				</span>
				<h1 class="mt-5 text-[52px] font-bold leading-[1.3] text-brand-roots">{{ __("Everything about your work, in your pocket.") }}</h1>
				<p class="mt-4 max-w-[520px] text-lg leading-8 text-brand-ink/80">
					{{ __("Check in, request leave, and follow your salary and your insights from your phone, or right here.") }}
				</p>

				<div class="mt-9 flex flex-wrap items-stretch gap-5">
					<div v-if="qr" class="flex items-center gap-4 rounded-[24px] bg-white p-4 shadow-card">
						<div class="h-[124px] w-[124px] shrink-0 overflow-hidden rounded-2xl [&>svg]:h-full [&>svg]:w-full" role="img" :aria-label="__('QR code of the app’s address')" v-html="qr" />
						<div class="max-w-[200px]">
							<div class="text-base font-bold text-brand-ink">{{ __("Open it on your phone") }}</div>
							<div class="mt-1.5 text-sm leading-6 text-brand-muted">{{ __("Scan the code with your phone’s camera, then add it to your home screen.") }}</div>
						</div>
					</div>
					<div class="flex flex-col justify-center gap-2">
						<button v-if="install.prompt" type="button" class="ms-primary-button px-6" @click="installNow">
							<AppIcon name="download" :size="20" />
							{{ __("Install on this computer") }}
						</button>
						<span class="ms-caption">{{ __("Works on phones, tablets and computers") }}</span>
					</div>
				</div>
			</div>
		</aside>
	</Teleport>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import { brand } from "@/data/brand"
import { install } from "@/data/ui"
import { installQr } from "@/data/pwa"

const __ = inject("$translate")

// Only wide screens show the panel, so only they ask for the QR code.
onMounted(() => {
	if (window.matchMedia("(min-width: 1024px)").matches) installQr.reload()
})
const qr = computed(() => installQr.data?.svg)

async function installNow() {
	const prompt = install.prompt
	if (!prompt) return
	prompt.prompt()
	await prompt.userChoice
	install.prompt = null
}
</script>
