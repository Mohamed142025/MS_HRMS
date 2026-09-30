import { ref } from "vue"
import { toast } from "frappe-ui"
import { __ } from "@/plugins/translationsPlugin"

// Downloads a salary slip's PDF through Frappe HR's download method.
export function useSalarySlipDownload() {
	const downloading = ref(false)

	function download(name) {
		downloading.value = true

		let headers = { "X-Frappe-Site-Name": window.location.hostname }
		if (window.csrf_token) {
			headers["X-Frappe-CSRF-Token"] = window.csrf_token
		}

		fetch("/api/method/hrms.api._download_pdf", {
			method: "POST",
			headers,
			body: new URLSearchParams({ doctype: "Salary Slip", docname: name }),
		})
			.then((response) => {
				if (!response.ok) throw new Error(response.statusText)
				return response.blob()
			})
			.then((blob) => {
				const blobUrl = window.URL.createObjectURL(blob)
				const link = document.createElement("a")
				link.href = blobUrl
				link.download = `${name}.pdf`
				link.click()
				setTimeout(() => window.URL.revokeObjectURL(blobUrl), 3000)
			})
			.catch((error) => {
				toast({
					title: __("Error"),
					text: __("Failed to download PDF: {0}", [error.message]),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			})
			.finally(() => {
				downloading.value = false
			})
	}

	return { download, downloading }
}
