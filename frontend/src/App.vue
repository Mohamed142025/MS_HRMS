<template>
	<ion-app>
		<ion-router-outlet id="main-content" />
		<Toasts />

		<InstallPrompt />
	</ion-app>
	<DesktopPanel />
</template>

<script setup>
import { onMounted } from "vue"
import { IonApp, IonRouterOutlet } from "@ionic/vue"

import { Toasts } from "frappe-ui"

import InstallPrompt from "@/components/InstallPrompt.vue"
import DesktopPanel from "@/components/DesktopPanel.vue"
import { showNotification } from "@/utils/pushNotifications"

onMounted(() => {
	window?.frappePushNotification?.onMessage((payload) => {
		showNotification(payload)
	})
})
</script>
