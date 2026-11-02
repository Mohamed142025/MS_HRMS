// This phone's id for check-ins (ms_hrms.checkin_guard): random, made once and kept by the
// app, so the site knows the phone an employee checks in from. Clearing the app's data
// makes a new one, which HR registers by resetting the employee's device.
const KEY = "ms_hrms:device_id"

export function deviceId() {
	try {
		let id = localStorage.getItem(KEY)
		if (!id) {
			id = crypto.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`
			localStorage.setItem(KEY, id)
		}
		return id
	} catch {
		return ""
	}
}
