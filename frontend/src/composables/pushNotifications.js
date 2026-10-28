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

// When turning notifications on or moving them fails on a device, the site logs why
// (ms_hrms.web_push.log_client_error).
export function reportPushError(step, error) {
	const text = `${step}: ${error?.name || ""} ${error?.message || error} · ${navigator.userAgent} · permission ${window.Notification?.permission}`
	console.error(text)
	return call("ms_hrms.web_push.log_client_error", { error: text }).catch(() => {})
}

async function subscribeHere(registration, quiet) {
	const key = await call("ms_hrms.web_push.get_public_key")
	let subscription = await registration.pushManager.getSubscription()
	// A subscription made with another key (keys made again) is replaced.
	const current = subscription?.options?.applicationServerKey
	if (subscription && current && encodeKey(current) !== key) {
		await subscription.unsubscribe()
		subscription = null
	}
	subscription ||= await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: applicationServerKey(key),
	})
	await call("ms_hrms.web_push.subscribe", { subscription: JSON.stringify(subscription.toJSON()), device: device(), quiet: quiet ? 1 : 0 })
}

function encodeKey(buffer) {
	return btoa(String.fromCharCode(...new Uint8Array(buffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

// The app's worker used to run in its assets folder, where Android shows its
// notifications as Chrome's. A device subscribed there is subscribed from the worker in
// the app's scope (main.js), quietly; only then is the old worker, and its subscription,
// dropped. If that fails, the old one keeps receiving and the move is tried next time.
export async function movePushSubscription(oldRegistrations, registration) {
	const subscribed = await Promise.all(oldRegistrations.map((old) => old.pushManager.getSubscription().catch(() => null)))
	if (subscribed.some(Boolean)) {
		if (Notification.permission !== "granted") throw new Error(`notification permission is ${Notification.permission}`)
		await subscribeHere(registration, true)
	}
	for (const [index, old] of oldRegistrations.entries()) {
		if (subscribed[index]) await call("ms_hrms.web_push.unsubscribe", { endpoint: subscribed[index].endpoint }).catch(() => {})
		await old.unregister()
	}
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
		await subscribeHere(await registration(), false)
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
				reportPushError(value ? "turn on" : "turn off", error)
				notify(false, error?.messages?.[0] || error?.message || __("Could not change notifications on this device"))
				if (value) enabled.value = false
			})
			.finally(() => (loading.value = false))
	}

	return { enabled, loading, available, disabled, description, toggle }
}
