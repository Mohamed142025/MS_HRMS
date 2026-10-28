import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

import dayjs from "@/utils/dayjs"
import { __ } from "@/plugins/translationsPlugin"


export const getDates = (shift) => {
	const fromDate = dayjs(shift.from_date).format("D MMM")
	const toDate = shift.to_date ? dayjs(shift.to_date).format("D MMM") : __("Ongoing")
	return fromDate == toDate ? fromDate : `${fromDate} - ${toDate}`
}

export const getTotalDays = (shift) => {
	if (!shift.to_date) return null
	const toDate = dayjs(shift.to_date)
	const fromDate = dayjs(shift.from_date)
	return toDate.diff(fromDate, "d") + 1
}

export const getShiftDates = (shift) => {
	const startDate = dayjs(shift.start_date).format("D MMM")
	const endDate = shift.end_date ? dayjs(shift.end_date).format("D MMM") : __("Ongoing")
	return startDate == endDate ? startDate : `${startDate} - ${endDate}`
}

export const getTotalShiftDays = (shift) => {
	if (!shift.end_date) return null
	const end_date = dayjs(shift.end_date)
	const start_date = dayjs(shift.start_date)
	return end_date.diff(start_date, "d") + 1
}

export const getShiftTiming = (shift) => {
	return (
		shift.start_time.split(":").slice(0, 2).join(":") +
		" - " +
		shift.end_time.split(":").splice(0, 2).join(":")
	)
}

const transformShiftRequests = (data) =>
	data.map((request) => {
		request.doctype = "Shift Request"
		request.shift_dates = getDates(request)
		request.total_shift_days = getTotalDays(request)
		return request
	})

export const myAttendanceRequests = createResource({
	// All the employee's requests, the cancelled ones included (ms_hrms.request_history).
	url: "ms_hrms.request_history.get_my_requests",
	params: { doctype: "Attendance Request" },
	auto: true,
	cache: "hrms:my_attendance_requests",
	transform(data) {
		return transformAttendanceRequests(data)
	}
})
const transformAttendanceRequests = (data) => {
		return data.map((request) => {
			request.doctype = "Attendance Request"
			request.attendance_dates = getDates(request)
			request.total_attendance_days = getTotalDays(request)
			return request
		})
}

const transformPermissionRequests = (data) => {
	return data.map((request) => {
		request.doctype = "Permission Request"
		request.permission_date_display = request.permission_date
		request.permission_time_range = [request.from_time, request.to_time]
		return request
	})
}

const transformOvertimeRequests = (data) => {
	return data.map((request) => {
		request.doctype = "Overtime Request"
		request.overtime_date_display = request.overtime_date
		request.overtime_time_range = [request.from_time, request.to_time]
		return request
	})
}

export const myPermissionRequests = createResource({
	url: "frappe.client.get_list",
	params: {
		doctype: "Permission Request",
		fields: [
			"name",
			"employee",
			"employee_name",
			"permission_date",
			"permission_type",
			"from_time",
			"to_time",
			"reason",
			"status",
			"docstatus",
			"creation",
		],
		filters: [["employee", "=", employeeResource.data.name]],
		// All the employee's requests, for My Requests to list and group.
		limit_page_length: 0,
		order_by: "creation desc",
	},
	auto: true,
	cache: "hrms:my_permission_requests",
	transform(data) {
		return transformPermissionRequests(data)
	},
})

export const teamPermissionRequests = createResource({
	// Awaiting the user's approval: of the employees whose requests they approve
	// (ms_hrms.request_approvers), not every request they may see.
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: {
		doctype: "Permission Request",
		fields: [
			"name",
			"employee",
			"employee_name",
			"permission_date",
			"permission_type",
			"from_time",
			"to_time",
			"reason",
			"status",
			"docstatus",
			"creation",
		],
	},
	auto: true,
	cache: "hrms:team_permission_requests",
	transform(data) {
		return transformPermissionRequests(data)
	},
})

export const myOvertimeRequests = createResource({
	url: "frappe.client.get_list",
	params: {
		doctype: "Overtime Request",
		fields: [
			"name",
			"employee",
			"employee_name",
			"overtime_date",
			"overtime_type",
			"from_time",
			"to_time",
			"requested_hours",
			"reason",
			"status",
			"docstatus",
			"creation",
		],
		filters: [["employee", "=", employeeResource.data.name]],
		// All the employee's requests, for My Requests to list and group.
		limit_page_length: 0,
		order_by: "creation desc",
	},
	auto: true,
	cache: "hrms:my_overtime_requests",
	transform(data) {
		return transformOvertimeRequests(data)
	},
})

export const teamOvertimeRequests = createResource({
	// Awaiting the user's approval: of the employees whose requests they approve
	// (ms_hrms.request_approvers), not every request they may see.
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: {
		doctype: "Overtime Request",
		fields: [
			"name",
			"employee",
			"employee_name",
			"overtime_date",
			"overtime_type",
			"from_time",
			"to_time",
			"requested_hours",
			"reason",
			"status",
			"docstatus",
			"creation",
		],
	},
	auto: true,
	cache: "hrms:team_overtime_requests",
	transform(data) {
		return transformOvertimeRequests(data)
	},
})

export const myShiftRequests = createResource({
	// All the employee's requests, the cancelled ones included (ms_hrms.request_history).
	url: "ms_hrms.request_history.get_my_requests",
	params: { doctype: "Shift Request" },
	auto: true,
	cache: "hrms:my_shift_requests",
	transform(data) {
		return transformShiftRequests(data)
	},
})

export const teamShiftRequests = createResource({
	// Awaiting the user's approval, theirs included when they approve them
	// (ms_hrms.request_approvers).
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: { doctype: "Shift Request" },
	auto: true,
	cache: "hrms:team_shift_requests",
	transform(data) {
		return transformShiftRequests(data)
	},
})
export const teamAttendanceRequests = createResource({
	// Awaiting the user's approval, theirs included when they approve them
	// (ms_hrms.request_approvers).
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: { doctype: "Attendance Request" },
	auto: true,
	cache: "hrms:team_attendance_requests",
	transform: (data) => {
		return transformAttendanceRequests(data)
	},
})
