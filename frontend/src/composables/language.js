// The signed-in user's language: saved on the user, and the app reloads in it.
import { ref } from "vue"
import { call, toast } from "frappe-ui"
import { __ } from "@/plugins/translationsPlugin"

export function useLanguage() {
	const current = window.frappe?.boot?.lang
	const changing = ref(false)

	function change(language) {
		if (language === current) return
		changing.value = true
		call("ms_hrms.pwa.set_language", { language })
			.then(() => window.location.reload())
			.catch((error) => {
				changing.value = false
				toast({
					title: __("Error"),
					text: error.messages?.[0] || error.message,
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			})
	}

	return { current, changing, change }
}
