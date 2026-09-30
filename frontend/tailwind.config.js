import frappeUIPreset from "frappe-ui/src/tailwind/preset"
export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			// The Digital Roots palette from ms_style's design tokens (ms_style/public/scss/
			// variables.scss, loaded through the ms_hrms_pwa_include_css hook), with the
			// same values as fallbacks for sites without it.
			colors: {
				brand: {
					roots: "rgba(var(--ms-roots-rgb, 14, 59, 46), <alpha-value>)",
					emerald: "rgba(var(--ms-emerald-rgb, 25, 123, 87), <alpha-value>)",
					mint: "rgba(var(--ms-mint-rgb, 52, 211, 153), <alpha-value>)",
					sand: "rgba(var(--ms-sand-rgb, 244, 241, 234), <alpha-value>)",
					ink: "rgba(var(--ms-ink-rgb, 22, 33, 28), <alpha-value>)",
					muted: "var(--ms-text-muted, #656C69)",
				},
				state: {
					success: "rgba(var(--ms-success-rgb, 25, 123, 87), <alpha-value>)",
					warning: "rgba(var(--ms-warning-rgb, 183, 121, 31), <alpha-value>)",
					danger: "rgba(var(--ms-danger-rgb, 194, 65, 59), <alpha-value>)",
					info: "rgba(var(--ms-info-rgb, 40, 122, 155), <alpha-value>)",
					"success-text": "var(--ms-success-text, #166A4B)",
					"warning-text": "var(--ms-warning-text, #875917)",
					"danger-text": "var(--ms-danger-text, #A73833)",
					"info-text": "var(--ms-info-text, #226783)",
				},
			},
			boxShadow: {
				card: "0 1px 2px rgba(var(--ms-shadow-rgb, 14, 59, 46), 0.06), 0 8px 24px rgba(var(--ms-shadow-rgb, 14, 59, 46), 0.06)",
				float: "0 14px 34px rgba(var(--ms-shadow-rgb, 14, 59, 46), 0.28)",
			},
			screens: {
				standalone: {
					raw: "(display-mode: standalone)",
				},
			},
			padding: {
				"safe-top": "env(safe-area-inset-top)",
				"safe-right": "env(safe-area-inset-right)",
				"safe-bottom": "env(safe-area-inset-bottom)",
				"safe-left": "env(safe-area-inset-left)",
			},
		},
	},
	plugins: [],
}
