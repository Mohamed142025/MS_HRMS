// Whether this phone is the employee's registered device (ms_hrms.checkin_guard): on
// another one the app is closed to them (App.vue, DeviceBlocked).
import { reactive } from "vue"
import { call } from "frappe-ui"

import { device as deviceName } from "@/composables/pushNotifications"
import { deviceId } from "@/utils/deviceId"

export const phone = reactive({ state: null, blocked: false })

export function checkPhone() {
	return call("ms_hrms.checkin_guard.register_device", { device: deviceId(), device_name: deviceName() })
		.then((result) => Object.assign(phone, { state: result?.state || null, blocked: Boolean(result?.blocked) }))
		.catch(() => {})
}
