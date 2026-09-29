import dayjs from "dayjs"
import updateLocale from "dayjs/plugin/updateLocale"
import localizedFormat from "dayjs/plugin/localizedFormat"
import relativeTime from "dayjs/plugin/relativeTime"
import isToday from "dayjs/plugin/isToday"
import isYesterday from "dayjs/plugin/isYesterday"
import isBetween from "dayjs/plugin/isBetween"

dayjs.extend(updateLocale)
dayjs.extend(localizedFormat)
dayjs.extend(relativeTime)
dayjs.extend(isToday)
dayjs.extend(isYesterday)
dayjs.extend(isBetween)

// Dates in the user's language. Arabic keeps Western digits, as the desk does.
import "dayjs/locale/ar"
const language = window.frappe?.boot?.lang || "en"
if (language.startsWith("ar")) {
	dayjs.updateLocale("ar", { preparse: (text) => text, postformat: (text) => text })
	dayjs.locale("ar")
}

export default dayjs
