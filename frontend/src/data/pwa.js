// The redesigned screens' numbers, worked out by ms_hrms.pwa_api (one call per screen).
import { createResource } from "frappe-ui"

const resource = (method, options = {}) =>
	createResource({ url: `ms_hrms.pwa_api.${method}`, cache: `ms_hrms:${method}`, ...options })

export const home = resource("get_home")
export const teamToday = resource("get_team_today")
export const leaveOverview = resource("get_leave_overview")
export const salary = resource("get_salary")
export const expenses = resource("get_expenses")
export const installQr = resource("get_install_qr")

export const attendanceMonth = createResource({ url: "ms_hrms.pwa_api.get_attendance" })
export const insights = createResource({ url: "ms_hrms.pwa_api.get_insights" })
