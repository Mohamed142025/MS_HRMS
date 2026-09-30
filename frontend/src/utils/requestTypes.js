// The request types the app handles: how each looks in lists (icon, tone, title,
// details), its status, and where to create one or see them all.
import dayjs from "@/utils/dayjs"
import { formatCurrency } from "@/utils/formatters"
import { __ } from "@/plugins/translationsPlugin"

// Icon tiles and status chips: brand tints for identity, status colors for state.
export const TONES = {
	emerald: "bg-brand-emerald/[.12] text-brand-emerald",
	roots: "bg-brand-roots/[.08] text-brand-roots",
	success: "bg-state-success/[.12] text-state-success-text",
	warning: "bg-state-warning/[.12] text-state-warning-text",
	danger: "bg-state-danger/[.12] text-state-danger-text",
	info: "bg-state-info/[.12] text-state-info-text",
	neutral: "bg-brand-roots/[.08] text-brand-ink/70",
}

export const REQUEST_TYPES = {
	"Leave Application": {
		icon: "sun",
		tone: "emerald",
		label: "Leaves",
		newRoute: "LeaveApplicationFormView",
		listRoute: "LeaveApplicationListView",
	},
	"Permission Request": {
		icon: "hourglass",
		tone: "warning",
		label: "Permissions",
		newRoute: "PermissionRequestNewView",
		listRoute: "PermissionRequestListView",
	},
	"Overtime Request": {
		icon: "clock-plus",
		tone: "info",
		label: "Overtime",
		newRoute: "OvertimeRequestNewView",
		listRoute: "OvertimeRequestListView",
	},
	"Expense Claim": {
		icon: "receipt",
		tone: "roots",
		label: "Expenses",
		newRoute: "ExpenseClaimFormView",
		listRoute: "ExpenseClaimListView",
	},
	"Employee Advance": {
		icon: "banknote",
		tone: "roots",
		label: "Advances",
		newRoute: "EmployeeAdvanceFormView",
		listRoute: "EmployeeAdvanceListView",
	},
	"Shift Request": {
		icon: "swap",
		tone: "emerald",
		label: "Shifts",
		newRoute: "ShiftRequestFormView",
		listRoute: "ShiftRequestListView",
	},
	"Attendance Request": {
		icon: "calendar-check",
		tone: "danger",
		label: "Attendance",
		newRoute: "AttendanceRequestFormView",
		listRoute: "AttendanceRequestListView",
	},
}

// The status each list shows, as Frappe HR's own list items worked it out.
export function requestStatus(doc) {
	if (doc.workflow_state_field) return doc[doc.workflow_state_field]
	switch (doc.doctype) {
		case "Expense Claim":
			if (doc.approval_status === "Rejected") return "Rejected"
			if (doc.status === "Paid" || doc.status === "Cancelled") return doc.status
			return doc.approval_status === "Approved" ? "Approved" : "Pending"
		case "Shift Request":
			return doc.docstatus ? doc.status : "Open"
		case "Attendance Request":
			return doc.docstatus ? "Submitted" : "Draft"
		case "Permission Request":
		case "Overtime Request":
			return doc.status || (doc.docstatus ? "Submitted" : "Draft")
		default:
			return doc.status
	}
}

const STATUS_TONES = {
	Approved: "success",
	Paid: "success",
	Claimed: "success",
	Open: "warning",
	Draft: "warning",
	Pending: "warning",
	"Pending Approval": "warning",
	Unpaid: "warning",
	"Partially Paid": "info",
	Submitted: "info",
	"Partly Claimed and Returned": "info",
	Returned: "neutral",
	Rejected: "danger",
	Cancelled: "neutral",
}

// A request type's name in lists and filters ("Leaves", "Permissions"...).
export const typeLabel = (doctype) => __(REQUEST_TYPES[doctype]?.label || doctype, null, "Request Type")

export const statusTone = (status) => TONES[STATUS_TONES[status] || "neutral"]

// Waiting for someone's decision.
export const isPending = (doc) =>
	["Open", "Draft", "Pending", "Pending Approval"].includes(requestStatus(doc)) && doc.docstatus === 0

export function requestTitle(doc) {
	switch (doc.doctype) {
		case "Leave Application":
			return __(doc.leave_type, null, "Leave Type")
		case "Permission Request":
			return doc.permission_type ? __(doc.permission_type) : __("Permission Request")
		case "Overtime Request":
			return __("Overtime Request")
		case "Expense Claim":
			return doc.expense_type ? __(doc.expense_type) : __("Expense Claim")
		case "Employee Advance":
			return doc.purpose || __("Employee Advance")
		case "Shift Request":
			return __(doc.shift_type)
		case "Attendance Request":
			return doc.reason ? __(doc.reason) : __("Attendance Request")
		default:
			return __(doc.doctype)
	}
}

const day = (value) => (value ? dayjs(value).format("ddd D MMM") : "")
const shortDay = (value) => (value ? dayjs(value).format("D MMM") : "")
const time = (value) => (value ? dayjs(`2000-01-01 ${value}`).format("h:mm a") : "")

function range(from, to) {
	if (!to || from === to) return day(from)
	return `${shortDay(from)} – ${shortDay(to)}`
}

export function requestDetails(doc) {
	switch (doc.doctype) {
		case "Leave Application": {
			const days = Number(doc.total_leave_days || 0)
			return [range(doc.from_date, doc.to_date), days ? __("{0} days", [days]) : ""].filter(Boolean).join(" · ")
		}
		case "Permission Request":
			return [day(doc.permission_date), doc.from_time ? `${time(doc.from_time)} – ${time(doc.to_time)}` : ""]
				.filter(Boolean)
				.join(" · ")
		case "Overtime Request":
			return [day(doc.overtime_date), doc.requested_hours ? __("{0} hours", [Number(doc.requested_hours)]) : ""]
				.filter(Boolean)
				.join(" · ")
		case "Expense Claim":
			return [shortDay(doc.posting_date), formatCurrency(doc.total_claimed_amount, doc.currency)]
				.filter(Boolean)
				.join(" · ")
		case "Employee Advance":
			return [shortDay(doc.posting_date), formatCurrency(doc.advance_amount || doc.paid_amount, doc.currency)]
				.filter(Boolean)
				.join(" · ")
		case "Shift Request":
			return range(doc.from_date, doc.to_date)
		case "Attendance Request":
			return range(doc.from_date, doc.to_date)
		default:
			return ""
	}
}
