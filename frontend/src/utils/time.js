// Times of day as the server sends them: Frappe returns a Time field as "9:00:00" (no
// leading zero before 10:00, sometimes with microseconds), which an <input type="time">
// refuses and shows blank, and which string slicing cuts wrong ("9:00:"). These helpers
// read any of "9:00", "09:00:00" or "9:00:00.000000".
import dayjs from "@/utils/dayjs"

// [hours, minutes, seconds] of a time of day, or null.
function parts(value) {
	if (value === null || value === undefined || value === "") return null
	const match = String(value).trim().match(/^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/)
	if (!match) return null
	return [Number(match[1]) % 24, Number(match[2]), Number(match[3] || 0)]
}

const pad = (number) => String(number).padStart(2, "0")

// "09:00:00": the time with leading zeros, as the server stores it.
export function normalizeTime(value) {
	const time = parts(value)
	return time ? time.map(pad).join(":") : ""
}

// "09:00" (or "09:00:30"): the value an <input type="time"> takes.
export function toTimeInput(value) {
	const time = parts(value)
	if (!time) return ""
	const [hours, minutes, seconds] = time
	return seconds ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}` : `${pad(hours)}:${pad(minutes)}`
}

// "09:00": hours and minutes, 24-hour.
export function shortTime(value) {
	const time = parts(value)
	return time ? `${pad(time[0])}:${pad(time[1])}` : ""
}

// "9:00 am": the time in the user's language.
export function formatTime(value, format = "h:mm a") {
	const time = parts(value)
	return time ? dayjs(`2000-01-01 ${time.map(pad).join(":")}`).format(format) : ""
}
