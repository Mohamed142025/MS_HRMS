<template>
	<ion-app>
		<ion-router-outlet id="main-content" />
		<Toasts />

		<InstallPrompt />
		<NotificationPrompt />
		<DeviceBlocked />
	</ion-app>
	<DesktopPanel />
</template>

<script setup>
import { onMounted, watch } from "vue"
import { IonApp, IonRouterOutlet } from "@ionic/vue"

import { Toasts } from "frappe-ui"

import InstallPrompt from "@/components/InstallPrompt.vue"
import NotificationPrompt from "@/components/NotificationPrompt.vue"
import DesktopPanel from "@/components/DesktopPanel.vue"
import { showNotification } from "@/utils/pushNotifications"
import DeviceBlocked from "@/components/DeviceBlocked.vue"
import { session } from "@/data/session"
import { checkPhone, phone } from "@/data/device"

// Signed in on this phone: it becomes the employee's device when they have none yet, and
// the app is closed to them on another one (ms_hrms.checkin_guard).
watch(
	() => session.isLoggedIn,
	(loggedIn) => (loggedIn ? checkPhone() : Object.assign(phone, { state: null, blocked: false })),
	{ immediate: true }
)

onMounted(() => {
	window?.frappePushNotification?.onMessage((payload) => {
		showNotification(payload)
	})
})
</script>
