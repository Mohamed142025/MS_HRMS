import { createResource } from "frappe-ui"

const transformAdvanceData = (data) => {
	return data.map((claim) => {
		claim.doctype = "Employee Advance"
		return claim
	})
}

export const advanceBalance = createResource({
	url: "hrms.api.get_employee_advance_balance",
	auto: true,
	cache: "hrms:employee_advance_balance",
	transform(data) {
		return transformAdvanceData(data)
	},
})

export const myAdvances = createResource({
	// All the employee's advances, the cancelled ones included (ms_hrms.request_history).
	url: "ms_hrms.request_history.get_my_requests",
	params: { doctype: "Employee Advance" },
	auto: true,
	cache: "hrms:my_advances",
	transform: transformAdvanceData,
})

export const teamAdvances = createResource({
	// Awaiting the user's approval: of the employees they manage or approve the expenses
	// of (ms_hrms.request_approvers).
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: { doctype: "Employee Advance" },
	auto: true,
	cache: "hrms:team_advances",
	transform: transformAdvanceData,
})
