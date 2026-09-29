// The site's branding and languages, sent with the page by ms_hrms.pwa (boot.brand).
const boot = window.frappe?.boot || {}

export const brand = {
	app_title: "Frappe HR",
	logo: null,
	icon: "/assets/hrms/manifest/favicon-196.png",
	...(boot.brand || {}),
}

export const languages = boot.languages || []
