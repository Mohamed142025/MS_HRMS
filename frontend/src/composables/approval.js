// Approving and rejecting requests from the approvals screen. The same calls Frappe HR's
// request sheet makes (RequestActionSheet): the decision is saved on the request's status
// field, and requests that are submitted afterwards (leave, expense claim, shift request)
// are submitted as a second, separate step. Attendance requests are approved by
// submitting them. Doctypes with a workflow are decided in the request sheet instead.
import { call } from "frappe-ui"

const FLOWS = {
	"Leave Application": { field: "status", submitAfter: true },
	"Expense Claim": { field: "approval_status", submitAfter: true },
	"Shift Request": { field: "status", submitAfter: true },
	"Permission Request": { field: "status", submitAfter: false },
	"Overtime Request": { field: "status", submitAfter: false },
	"Attendance Request": { field: null, submitAfter: true },
}

export const approvalFlow = (doctype) => FLOWS[doctype]

export function decide(doc, decision) {
	const flow = FLOWS[doc.doctype]
	return call("frappe.client.set_value", {
		doctype: doc.doctype,
		name: doc.name,
		fieldname: flow.field,
		value: decision,
	})
}

export async function canSubmit(doc) {
	const result = await call("frappe.client.get_doc_permissions", { doctype: doc.doctype, docname: doc.name })
	return Boolean(result?.permissions?.submit)
}

// As a set of values: set_value refuses docstatus as a single field name.
export function submit(doc) {
	return call("frappe.client.set_value", {
		doctype: doc.doctype,
		name: doc.name,
		fieldname: { docstatus: 1 },
	})
}
