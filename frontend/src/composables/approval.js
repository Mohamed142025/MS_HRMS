// Approving and rejecting requests from the approvals screen. The same calls Frappe HR's
// request sheet makes (RequestActionSheet): the decision is saved on the request's status
// field (through ms_hrms.request_approvers.decide, which also keeps the approver's remarks),
// and requests that are submitted afterwards (leave, expense claim, shift request)
// are submitted as a second, separate step. Attendance requests are approved by
// submitting them, and so are Employee Advances, through ms_hrms' approver check
// (ms_hrms.request_approvers.approve) as Frappe HR leaves them to a role. Permission and
// Overtime Requests, which the Employee role may not
// write, are decided through ms_hrms' approver check (ms_hrms.request_approvers.decide).
// Attendance Requests and Employee Advances, which have no rejected state, are rejected
// through decide too: they stay drafts, recorded as rejected.
// Doctypes with a workflow are decided in the request sheet instead (WorkflowActionSheet).
import { call } from "frappe-ui"
import { alertController } from "@ionic/vue"

import { __ } from "@/plugins/translationsPlugin"

const FLOWS = {
	"Leave Application": { field: "status", submitAfter: true },
	"Expense Claim": { field: "approval_status", submitAfter: true },
	"Shift Request": { field: "status", submitAfter: true },
	"Permission Request": { field: "status", submitAfter: false },
	"Overtime Request": { field: "status", submitAfter: false },
	"Attendance Request": { field: null, submitAfter: true, approveMethod: "ms_hrms.request_approvers.approve" },
	"Employee Advance": { field: null, submitAfter: true, approveMethod: "ms_hrms.request_approvers.approve" },
}

export const approvalFlow = (doctype) => FLOWS[doctype]

// The decision, with the approver's remarks (the reason, when rejecting), which the
// employee sees on the request and in its notification.
export function decide(doc, decision, remarks = "") {
	return call("ms_hrms.request_approvers.decide", {
		doctype: doc.doctype,
		name: doc.name,
		status: decision,
		remarks: remarks || "",
	})
}

// Asks the approver why they reject the request (optional). Resolves to the reason ("" for
// none), or null when they think again.
export async function askRejectionReason() {
	const alert = await alertController.create({
		header: __("Reject this request?"),
		message: __("You may give the reason. The employee sees it on the request and in its notification."),
		cssClass: "ms-reject-alert",
		inputs: [
			{
				name: "reason",
				type: "textarea",
				placeholder: __("Reason for rejection (optional)"),
				attributes: { maxlength: 500, rows: 3 },
			},
		],
		buttons: [
			{ text: __("Cancel"), role: "cancel" },
			{ text: __("Reject"), role: "confirm", cssClass: "ms-alert-danger" },
		],
	})
	await alert.present()
	const { data, role } = await alert.onDidDismiss()
	if (role !== "confirm") return null
	return (data?.values?.reason || "").trim()
}

export async function canSubmit(doc) {
	const result = await call("frappe.client.get_doc_permissions", { doctype: doc.doctype, docname: doc.name })
	return Boolean(result?.permissions?.submit)
}

// As a set of values: set_value refuses docstatus as a single field name.
export function submit(doc) {
	const approveMethod = FLOWS[doc.doctype]?.approveMethod
	if (approveMethod) return call(approveMethod, { doctype: doc.doctype, name: doc.name })
	return call("frappe.client.set_value", {
		doctype: doc.doctype,
		name: doc.name,
		fieldname: { docstatus: 1 },
	})
}
