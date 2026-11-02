<template>
	<!-- Asking for notifications: offered a moment after each opening of the app to a
	     signed-in employee whose device does not get them, with what they are for. The
	     browser's own question comes from the button, as browsers require; a device where
	     they were blocked is shown where to allow them, since the app may not ask again. -->
	<ion-modal :is-open="open" :initial-breakpoint="1" :breakpoints="[0, 1]" class="ms-sheet" @didDismiss="later">
		<div class="bg-white px-5 pb-[max(24px,env(safe-area-inset-bottom))] pt-6">
			<div class="flex items-center gap-3.5">
				<span class="flex h-16 w-16 shrink-0 items-center justify-center rounded-[18px] bg-brand-emerald text-white shadow-[0_8px_18px_rgba(var(--ms-emerald-rgb,25,123,87),0.3)]">
					<AppIcon name="bell" :size="30" :stroke-width="2" />
				</span>
				<div>
					<h2 class="text-[20px] font-bold text-brand-ink">{{ __("Turn on notifications") }}</h2>
					<p class="ms-caption">{{ __("So nothing that concerns you is missed") }}</p>
				</div>
			</div>

			<ul class="mt-[18px] flex flex-col gap-2.5">
				<li
					v-for="reason in reasons"
					:key="reason.text"
					class="flex items-center gap-3 rounded-2xl border border-brand-roots/[.08] bg-brand-sand/50 px-3 py-2.5 text-[14.5px] text-brand-ink"
				>
					<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-brand-roots/[.12] bg-white text-brand-roots">
						<AppIcon :name="reason.icon" :size="19" />
					</span>
					{{ reason.text }}
				</li>
			</ul>

			<template v-if="blocked">
				<p class="mt-4 text-[14px] font-semibold text-brand-ink">{{ __("Notifications are blocked on this device. To allow them:") }}</p>
				<ol class="mt-2.5 flex flex-col gap-2">
					<li v-for="(step, index) in blockedSteps" :key="index" class="flex items-center gap-3 text-[14px] text-brand-ink">
						<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-roots text-[13px] font-bold text-brand-sand">
							{{ index + 1 }}
						</span>
						{{ step }}
					</li>
				</ol>
			</template>
			<p v-else class="mt-4 flex items-center gap-2 text-[13px] text-brand-ink/70">
				<AppIcon name="lock" :size="15" class="shrink-0" />
				{{ __("Only what concerns you. You can turn them off anytime from Settings.") }}
			</p>

			<div class="mt-[18px] flex gap-2.5">
				<button type="button" class="ms-primary-button grow" :disabled="loading" @click="turnOn">
					<AppIcon :name="blocked ? 'refresh' : 'bell'" :size="20" />
					{{ blocked ? __("I allowed them") : __("Turn on notifications") }}
				</button>
				<button type="button" class="h-14 w-[110px] shrink-0 rounded-[18px] bg-brand-sand text-[15px] font-semibold text-brand-roots" @click="later">
					{{ __("Later") }}
				</button>
			</div>
		</div>
	</ion-modal>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from "vue"
import { IonModal } from "@ionic/vue"
import { toast } from "frappe-ui"

import AppIcon from "@/components/ui/AppIcon.vue"
import { usePushNotifications } from "@/composables/pushNotifications"
import { session } from "@/data/session"
import { brand } from "@/data/brand"
import { install } from "@/data/ui"

const __ = inject("$translate")
const { enabled, checked, available, loading, toggle } = usePushNotifications()

const reasons = [
	{ icon: "calendar-check", text: __("Know as soon as your leave or permission is approved") },
	{ icon: "wallet", text: __("Your salary slip the moment it is ready") },
	{ icon: "check", text: __("Requests waiting for your approval, if you approve for your team") },
	{ icon: "bell", text: __("Reminders and announcements from HR") },
]

const open = ref(false)
const permission = ref(window.Notification?.permission)
const blocked = computed(() => permission.value === "denied")

// Where a blocked device allows notifications again: the phone's settings for an app on
// the home screen, the site's settings in a browser.
const blockedSteps = computed(() => {
	if (install.standalone && install.platform === "ios")
		return [__("Open the iPhone Settings"), __("Tap Notifications, then {0}", [brand.app_title]), __("Turn on Allow Notifications")]
	if (install.standalone)
		return [__("Press and hold the app icon, then tap App info"), __("Tap Notifications"), __("Turn on notifications for {0}", [brand.app_title])]
	return [__("Tap the icon beside the address bar"), __("Open Permissions, then Notifications"), __("Choose Allow, then come back here")]
})

// Asked on every opening of the app until this device gets notifications, whether they
// were never turned on, turned off in the app, or blocked. "Later" waits for the next
// opening.
const LATER = "ms_hrms:notifications_prompt_later"
const askedThisOpening = () => {
	try {
		return sessionStorage.getItem(LATER) === "1"
	} catch {
		return false
	}
}
const shouldAsk = () => {
	permission.value = window.Notification?.permission
	return session.isLoggedIn && available.value && checked.value && !enabled.value && !askedThisOpening()
}

function later() {
	if (!open.value) return
	open.value = false
	try {
		sessionStorage.setItem(LATER, "1")
	} catch {
		// private browsing: asked again on the next change
	}
}

async function turnOn() {
	permission.value = window.Notification?.permission
	if (blocked.value) {
		toast({
			title: __("Error"),
			text: __("Notifications are still blocked on this device"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
		return
	}
	await toggle(true)
	permission.value = window.Notification?.permission
	// Turned on, or refused in the browser's own question: asked again on the next opening.
	if (enabled.value || blocked.value) later()
}

// A moment after the app opens or after signing in, and never over the install sheet.
let timer = null
watch(
	() => [session.isLoggedIn, install.open, checked.value],
	() => {
		clearTimeout(timer)
		if (open.value || install.open || !shouldAsk()) return
		timer = setTimeout(() => {
			if (!install.open && shouldAsk()) open.value = true
		}, 2500)
	},
	{ immediate: true }
)
onBeforeUnmount(() => clearTimeout(timer))
</script>
