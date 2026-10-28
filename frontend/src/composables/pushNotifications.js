// Turning push notifications on and off for this device, shared by the profile and settings
// screens. They are sent by the site itself (ms_hrms.web_push, Web Push with the site's
// VAPID key), so they work wherever ms_hrms is installed; the device subscribes through
// the app's service worker (main.js) and the site keeps the subscription.
import { computed, ref } from "vue"
import { call, toast } from "frappe-ui"

import { __ } from "@/plugins/translationsPlugin"

// Web Push in this browser: Android's Chrome, desktop browsers, and an iPhone's
// home screen app (iOS 16.4 and later).
export const pushSupported = () =>
	"serviceWorker" in navigator && "PushManager" in window && "Notification" in window

const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
const isStandalone = () =>
	window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true

async function registration() {
	const registered = await window.msHrmsServiceWorker
	if (!registered) throw new Error(__("The app's service worker is not running. Reload the app and try again."))
	return registered
}

function applicationServerKey(base64) {
	const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/")
	return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0))
}

function device() {
	const agent = navigator.userAgent
	const os = /android/i.test(agent) ? "Android" : isIOS() ? "iOS" : /windows/i.test(agent) ? "Windows" : /mac/i.test(agent) ? "macOS" : "Linux"
	const browser = /edg\//i.test(agent) ? "Edge" : /chrome|crios/i.test(agent) ? "Chrome" : /firefox|fxios/i.test(agent) ? "Firefox" : /safari/i.test(agent) ? "Safari" : ""
	return [os, browser, isStandalone() ? "app" : ""].filter(Boolean).join(" · ")
}

// The app's worker used to run in its assets folder, where Android shows its
// notifications as Chrome's: a device subscribed there is subscribed again from the
// worker in the app's scope (main.js), quietly, and the old subscription is dropped.
export async function takeOverSubscription(oldRegistration) {
	const old = await oldRegistration.pushManager.getSubscription().catch(() => null)
	if (!old) return false
	await call("ms_hrms.web_push.unsubscribe", { endpoint: old.endpoint }).catch(() => {})
	await old.unsubscribe().catch(() => {})
	return true
}

export async function subscribeAgain(registration) {
	if (!pushSupported() || Notification.permission !== "granted") return
	const key = await call("ms_hrms.web_push.get_public_key")
	const subscription =
		(await registration.pushManager.getSubscription()) ||
		(await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: applicationServerKey(key) }))
	await call("ms_hrms.web_push.subscribe", { subscription: JSON.stringify(subscription.toJSON()), device: device(), quiet: 1 })
}

export function usePushNotifications() {
	const enabled = ref(false)
	const loading = ref(false)

	// On an iPhone, Web Push needs the app added to the home screen.
	const available = computed(() => pushSupported() && !(isIOS() && !isStandalone()))
	const disabled = computed(() => !available.value || loading.value)
	const description = computed(() => {
		if (isIOS() && !isStandalone()) return __("Add the app to your home screen to get notifications on iPhone")
		if (!pushSupported()) return __("This browser does not support notifications")
		if (window.Notification?.permission === "denied") return __("Notifications are blocked for this app in the browser settings")
		return ""
	})

	// Whether this device is subscribed on the site.
	if (available.value) {
		registration()
			.then((registered) => registered.pushManager.getSubscription())
			.then(async (subscription) => {
				enabled.value = Boolean(subscription) && (await call("ms_hrms.web_push.is_subscribed", { endpoint: subscription.endpoint }))
			})
			.catch(() => (enabled.value = false))
	}

	const notify = (ok, text) =>
		toast({
			title: ok ? __("Success") : __("Error"),
			text,
			icon: ok ? "check-circle" : "alert-circle",
			position: "bottom-center",
			iconClasses: ok ? "text-green-500" : "text-red-500",
		})

	async function turnOn() {
		const permission = await Notification.requestPermission()
		if (permission !== "granted") {
			notify(false, __("Push Notification permission denied"))
			return false
		}
		const registered = await registration()
		const key = await call("ms_hrms.web_push.get_public_key")
		let subscription = await registered.pushManager.getSubscription()
		// A subscription made with another key (another site, or keys made again) is replaced.
		const current = subscription?.options?.applicationServerKey
		if (subscription && current && btoa(String.fromCharCode(...new Uint8Array(current))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "") !== key) {
			await subscription.unsubscribe()
			subscription = null
		}
		subscription ||= await registered.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey: applicationServerKey(key),
		})
		await call("ms_hrms.web_push.subscribe", { subscription: JSON.stringify(subscription.toJSON()), device: device() })
		notify(true, __("Push notifications enabled"))
		return true
	}

	async function turnOff() {
		const registered = await registration()
		const subscription = await registered.pushManager.getSubscription()
		if (subscription) {
			await call("ms_hrms.web_push.unsubscribe", { endpoint: subscription.endpoint })
			await subscription.unsubscribe()
		}
		notify(true, __("Push notifications disabled"))
		return false
	}

	function toggle(value) {
		loading.value = true
		return (value ? turnOn() : turnOff())
			.then((state) => (enabled.value = state))
			.catch((error) => {
				notify(false, error?.messages?.[0] || error?.message || __("Could not change notifications on this device"))
				if (value) enabled.value = false
			})
			.finally(() => (loading.value = false))
	}

	return { enabled, loading, available, disabled, description, toggle }
}
