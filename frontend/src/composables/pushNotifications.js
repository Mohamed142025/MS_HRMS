// Turning push notifications on and off for this device (Frappe push relay), as the
// settings screen always did; shared by the profile and settings screens.
import { computed, ref } from "vue"
import { toast } from "frappe-ui"

import { arePushNotificationsEnabled } from "@/data/notifications"
import { __ } from "@/plugins/translationsPlugin"

export function usePushNotifications() {
	const enabled = ref(window.frappePushNotification?.isNotificationEnabled())
	const loading = ref(false)

	const available = computed(() => Boolean(window.frappe?.boot.push_relay_server_url && arePushNotificationsEnabled.data))
	const disabled = computed(() => !available.value || loading.value)
	const description = computed(() => (available.value ? "" : __("Push notifications have been disabled on your site")))

	const notify = (ok, text) =>
		toast({
			title: ok ? __("Success") : __("Error"),
			text,
			icon: ok ? "check-circle" : "alert-circle",
			position: "bottom-center",
			iconClasses: ok ? "text-green-500" : "text-red-500",
		})

	function toggle(value) {
		loading.value = true
		const action = value
			? window.frappePushNotification.enableNotification().then((data) => {
					if (data.permission_granted) {
						enabled.value = true
					} else {
						enabled.value = false
						notify(false, __("Push Notification permission denied"))
					}
			  })
			: window.frappePushNotification.disableNotification().then(() => {
					enabled.value = false
					notify(true, __("Push notifications disabled"))
			  })

		return action
			.catch((error) => {
				notify(false, __(error.message))
				if (value) enabled.value = false
			})
			.finally(() => {
				loading.value = false
			})
	}

	return { enabled, loading, available, disabled, description, toggle }
}
