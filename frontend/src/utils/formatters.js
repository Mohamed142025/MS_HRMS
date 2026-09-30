import { createDocumentResource } from "frappe-ui"

import dayjs from "@/utils/dayjs"
import { __ } from "@/plugins/translationsPlugin.js"

const settings = createDocumentResource({
	doctype: "System Settings",
	name: "System Settings",
	auto: false,
})

export const formatCurrency = (value, currency) => {
	if (!currency) return value

	// hack: if value contains a space, it is already formatted
	if (value?.toString().trim().includes(" ")) return value

	const locale = settings.doc?.country == "India" ? "en-IN" : settings.doc?.language

	const formatter = Intl.NumberFormat(locale, {
		style: "currency",
		currency: currency,
		trailingZeroDisplay: "stripIfInteger",
		currencyDisplay: "narrowSymbol",
	})
	return (
		formatter
			.format(value)
			// add space between the digits and symbol
			.replace(/^(\D+)/, "$1 ")
			// remove extra spaces if any (added by some browsers)
			.replace(/\s+/, " ")
	)
}

export const formatTimestamp = (timestamp) => {
	const formattedTime = dayjs(timestamp).format("hh:mm a")

	if (dayjs(timestamp).isToday()) return formattedTime
	else if (dayjs(timestamp).isYesterday()) return __("{0} yesterday", [formattedTime])
	else if (dayjs(timestamp).isSame(dayjs(), "year"))
		return __("{0} on {1}", [formattedTime, dayjs(timestamp).format("D MMM")])

	return __("{0} on {1}", [formattedTime, dayjs(timestamp).format("D MMM, YYYY")])
}

// Amounts in the redesigned screens: Western digits with thousands separators, and the
// currency as a translated word after the number ("4,733 EGP" / "4,733 ج.م").
export const formatNumber = (value, maximumFractionDigits = 2) =>
	Intl.NumberFormat("en-US", { maximumFractionDigits }).format(Number(value || 0))

export const formatAmount = (value, currency) =>
	currency ? `${formatNumber(value)} ${__(currency)}` : formatNumber(value)
