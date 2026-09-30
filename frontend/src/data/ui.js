import { reactive } from "vue"

// The "new request" sheet, opened from the tab bar's middle button and the home screen.
export const newRequestSheet = reactive({ open: false })

// Amounts on the finance screens can be hidden (remembered on this device).
const HIDE_AMOUNTS = "ms_hrms:hide_amounts"
const readHidden = () => {
	try {
		return localStorage.getItem(HIDE_AMOUNTS) === "1"
	} catch {
		return false
	}
}
export const privacy = reactive({
	hidden: readHidden(),
	toggle() {
		this.hidden = !this.hidden
		try {
			localStorage.setItem(HIDE_AMOUNTS, this.hidden ? "1" : "0")
		} catch {
			// private browsing: the choice lasts for this visit
		}
	},
})

// Installing the app: the browser's install prompt (Chrome, Edge, Android) when it offers
// one, and the sheet with the steps (Safari on iPhone and iPad has no prompt).
const isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent)
export const install = reactive({
	open: false,
	prompt: null,
	platform: isIos ? "ios" : "android",
	standalone: Boolean(window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone),
})

window.addEventListener("beforeinstallprompt", (event) => {
	event.preventDefault()
	install.prompt = event
})

window.addEventListener("appinstalled", () => {
	install.prompt = null
	install.open = false
	install.standalone = true
})
