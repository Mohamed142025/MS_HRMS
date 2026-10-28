import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"
import { initSocket } from "./socket"

import {
	Button,
	Input,
	setConfig,
	frappeRequest,
	resourcesPlugin,
	FormControl,
} from "frappe-ui"
import { translationsPlugin } from "./plugins/translationsPlugin.js"
import EmptyState from "@/components/EmptyState.vue"

import { IonicVue } from "@ionic/vue"

import { session } from "@/data/session"
import { userResource } from "@/data/user"
import { employeeResource } from "@/data/employee"

import dayjs from "@/utils/dayjs"
import getIonicConfig from "@/utils/ionicConfig"

import FrappePushNotification from "../public/frappe-push-notification"
import { movePushSubscription, reportPushError } from "@/composables/pushNotifications"

/* Core CSS required for Ionic components to work properly */
import "@ionic/vue/css/core.css"

/* Theme variables */
import "./theme/variables.css"

import "./main.css"

const app = createApp(App)
const socket = initSocket()

setConfig("resourceFetcher", frappeRequest)
app.use(resourcesPlugin)
app.use(translationsPlugin)

app.component("Button", Button)
app.component("Input", Input)
app.component("FormControl", FormControl)
app.component("EmptyState", EmptyState)

app.use(router)
app.use(IonicVue, getIonicConfig())

if (session?.isLoggedIn && !employeeResource?.data) {
	employeeResource.reload()
}

app.provide("$session", session)
app.provide("$user", userResource)
app.provide("$employee", employeeResource)
app.provide("$socket", socket)
app.provide("$dayjs", dayjs)

const registerServiceWorker = async () => {
	window.frappePushNotification = new FrappePushNotification("hrms")

	if ("serviceWorker" in navigator) {
		// Served by ms_hrms.pwa within the app's scope, so Android shows the app's
		// notifications as the installed app's, with its icon.
		let serviceWorkerURL = "/hrms/sw.js"
		// This app's workers from its assets folder, kept until their push subscription
		// has moved to the worker in the app's scope.
		const assetsWorkers = []

		// Workers left by earlier builds of this app (Frappe HR's own, or one registered
		// for the whole site) serve stale files; other apps' workers are left alone.
		try {
			const registrations = await navigator.serviceWorker.getRegistrations()
			for (const registration of registrations) {
				const script = (registration.active || registration.waiting || registration.installing)?.scriptURL || ""
				if (script.includes("/assets/ms_hrms/frontend/sw.js")) {
					assetsWorkers.push(registration)
					continue
				}
				const stale =
					script.includes("/assets/hrms/frontend/") ||
					(script.includes("/frontend/sw.js") && new URL(registration.scope).pathname === "/")
				if (stale) await registration.unregister()
			}
		} catch (err) {
			console.error("Failed to unregister stale service workers", err)
		}

		let config = ""

		if (window.frappe?.boot?.push_relay_server_url) {
			try {
				config = await window.frappePushNotification.fetchWebConfig()
				serviceWorkerURL = `${serviceWorkerURL}?config=${encodeURIComponent(
					JSON.stringify(config)
				)}`
			} catch (err) {
				console.error("Failed to fetch FCM config", err)
			}
		}

		// Kept for turning push notifications on (composables/pushNotifications.js).
		window.msHrmsServiceWorker = navigator.serviceWorker.register(serviceWorkerURL, {
			type: "classic",
			scope: "/hrms",
		})
		if (assetsWorkers.length) {
			window.msHrmsServiceWorker
				.then(() => navigator.serviceWorker.ready)
				.then((registration) => movePushSubscription(assetsWorkers, registration))
				.catch((err) => reportPushError("move to the app's worker", err))
		}
		window.msHrmsServiceWorker
			.then((registration) => {
				if (config) {
					window.frappePushNotification.initialize(registration).then(() => {
						console.log("Frappe Push Notification initialized")
					})
				}
			})
			.catch((err) => {
				console.error("Failed to register service worker", err)
			})
	} else {
		console.error("Service worker not enabled/supported by the browser")
	}
}

router.isReady().then(async () => {
	if (import.meta.env.DEV) {
		await frappeRequest({
			url: "/api/method/ms_hrms.pwa.get_context_for_dev",
		}).then(async (values) => {
			if (!window.frappe) window.frappe = {}
			window.frappe.boot = values
		})
	}

	await translationsPlugin.isReady();
	registerServiceWorker()
	app.mount("#app")
	hideSplash()
})

// The launch screen in index.html fades out once the first screen is up.
function hideSplash() {
	const splash = document.getElementById("ms-splash")
	if (!splash) return
	requestAnimationFrame(() => splash.classList.add("is-hidden"))
	setTimeout(() => splash.remove(), 400)
}

router.beforeEach(async (to, _, next) => {
	let isLoggedIn = session.isLoggedIn

	try {
		if (isLoggedIn) await userResource.reload()
	} catch (error) {
		isLoggedIn = false
	}

	if (!isLoggedIn) {
		// password reset page is outside the PWA scope
		if (to.path === "/update-password") {
			return next(false)
		} else if (!["Login", "ForgotPassword"].includes(to.name)) {
			return next({ name: "Login" })
		}
	}

	if (isLoggedIn && to.name !== "InvalidEmployee") {
		await employeeResource.promise
		// user should be an employee to access the app
		// since all views are employee specific
		if (
			!employeeResource?.data ||
			employeeResource?.data?.user_id !== userResource.data.name
		) {
			next({ name: "InvalidEmployee" })
		} else if (["Login", "ForgotPassword"].includes(to.name)) {
			next({ name: "Home" })
		} else {
			next()
		}
	} else {
		next()
	}
})
