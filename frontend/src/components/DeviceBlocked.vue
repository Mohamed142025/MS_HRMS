<template>
	<!-- The app on a phone that is not the employee's registered one: closed to them until
	     HR registers it (ms_hrms.checkin_guard). -->
	<div
		v-if="phone.blocked"
		class="fixed inset-0 z-[100000] flex flex-col items-center justify-center gap-4 bg-brand-sand px-6 text-center"
		role="alertdialog"
		aria-modal="true"
		:aria-label="__('Another Phone')"
	>
		<span class="flex h-20 w-20 items-center justify-center rounded-[24px] bg-state-danger/[.12] text-state-danger-text">
			<AppIcon name="lock" :size="38" :stroke-width="2" />
		</span>
		<h1 class="text-[22px] font-bold text-brand-ink">{{ __("This phone is not your registered device") }}</h1>
		<p class="max-w-[340px] text-[15px] leading-7 text-brand-ink/75">
			{{ __("You can use the app only on the phone registered to you. To use this phone, ask HR to reset your device, then open the app here again.") }}
		</p>
		<button type="button" class="ms-primary-button mt-2 w-full max-w-[340px]" @click="checkPhone">
			<AppIcon name="refresh" :size="20" />
			{{ __("Try Again") }}
		</button>
		<button type="button" class="ms-link" @click="session.logout.submit()">{{ __("Log Out") }}</button>
	</div>
</template>

<script setup>
import { inject } from "vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import { checkPhone, phone } from "@/data/device"
import { session } from "@/data/session"

const __ = inject("$translate")
</script>
