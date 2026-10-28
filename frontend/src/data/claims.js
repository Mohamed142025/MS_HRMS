import { createResource } from "frappe-ui"
import { reactive } from "vue"

export const expenseClaimSummary = createResource({
	url: "hrms.api.get_expense_claim_summary",
	auto: true,
	cache: "hrms:expense_claim_summary",
})

const transformClaimData = (data) => {
	return data.map((claim) => {
		claim.doctype = "Expense Claim"
		return claim
	})
}

export const myClaims = createResource({
	// All the employee's requests, the cancelled ones included (ms_hrms.request_history).
	url: "ms_hrms.request_history.get_my_requests",
	params: { doctype: "Expense Claim" },
	auto: true,
	cache: "hrms:my_claims",
	transform(data) {
		return transformClaimData(data)
	},
	onSuccess() {
		expenseClaimSummary.reload()
	},
})

export const teamClaims = createResource({
	// Awaiting the user's approval, theirs included when they approve them
	// (ms_hrms.request_approvers).
	url: "ms_hrms.request_approvers.get_requests_to_approve",
	params: { doctype: "Expense Claim" },
	auto: true,
	cache: "hrms:team_claims",
	transform(data) {
		return transformClaimData(data)
	},
})

export let claimTypesByID = reactive({})

export const claimTypesResource = createResource({
	url: "hrms.api.get_expense_claim_types",
	auto: true,
	transform(data) {
		return data.map((row) => {
			claimTypesByID[row.name] = row
			return row
		})
	},
})
