// Repayment plans of employee advances (advance_repayment.py): HR sets one on the form
// once the manager approves, then moves the remaining installments on or postpones one.
const REPAYMENT = "ms_hrms.advance_repayment";
const SCHEDULE = "custom_repayment_schedule";
const STATUS_COLORS = { Scheduled: "blue", Due: "orange", Deducted: "green", Missed: "red" };

frappe.ui.form.on("Employee Advance", {
	refresh(frm) {
		// The employee's manager or approver approves (submits) it, whatever their roles
		// (ms_hrms.request_approvers.approve).
		if (frm.doc.docstatus === 0 && !frm.is_new() && frm.doc.__onload?.ms_hrms_can_approve) {
			frm.page.set_primary_action(__("Approve"), () =>
				frappe.confirm(__("Approve this advance?"), () =>
					frappe.call({
						method: "ms_hrms.request_approvers.approve",
						args: { doctype: frm.doctype, name: frm.doc.name },
						freeze: true,
						callback: () => frm.reload_doc(),
					})
				)
			);
		}

		const grid = frm.fields_dict[SCHEDULE]?.grid;
		if (!grid) return;
		grid.update_docfield_property("status", "formatter", (value) =>
			value
				? `<span class="indicator-pill ${STATUS_COLORS[value] || "gray"}">${__(value)}</span>`
				: ""
		);

		const can_plan = frm.doc.docstatus === 1 && frm.doc.__onload?.ms_hrms_can_plan_repayment;
		for (const field of [SCHEDULE, "custom_repayment_months", "custom_repayment_start"]) {
			frm.set_df_property(field, "read_only", can_plan ? 0 : 1);
		}
		grid.refresh();
		show_missed(frm);
		if (!can_plan) return;

		const rows = frm.doc[SCHEDULE] || [];
		const group = __("Repayment Plan");
		if (rows.some((row) => ["Scheduled", "Missed"].includes(row.status))) {
			frm.add_custom_button(__("Move Remaining Installments"), () => move_remaining(frm), group);
		}
		if (rows.some((row) => row.status !== "Deducted")) {
			frm.add_custom_button(__("Postpone an Installment"), () => postpone(frm), group);
		}
	},
});

function month_label(date) {
	return moment(date).locale(frappe.boot.lang || "en").format("MMMM YYYY");
}

function this_month() {
	return moment().startOf("month").format("YYYY-MM-DD");
}

function call(frm, method, args) {
	return frappe.call({
		method: `${REPAYMENT}.${method}`,
		args: { name: frm.doc.name, ...args },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}

function show_missed(frm) {
	const rows = frm.doc[SCHEDULE] || [];
	const missed = rows.filter((row) => row.status === "Missed");
	if (frm.doc.docstatus !== 1) return;
	// Nothing is deducted beyond what was paid (advance_repayment.send_due).
	const sent = rows.filter((row) => ["Due", "Deducted"].includes(row.status)).reduce((sum, row) => sum + row.amount, 0);
	const unpaid = rows.some((row) => row.status === "Scheduled") && (frm.doc.paid_amount || 0) - (frm.doc.claimed_amount || 0) - sent <= 0;
	if (!missed.length && unpaid) {
		frm.dashboard.set_headline_alert(
			__("The installments wait for the advance to be paid: nothing is deducted from the salary before it is."),
			"blue"
		);
	}
	if (!missed.length) return;
	frm.dashboard.set_headline_alert(
		__("Not deducted: {0}. Move the remaining installments or postpone them.", [
			missed.map((row) => month_label(row.payroll_date)).join(", "),
		]),
		"red"
	);
}

function move_remaining(frm) {
	// After the last installment sent to payroll, and not before this month.
	const sent = (frm.doc[SCHEDULE] || []).filter((row) => ["Due", "Deducted"].includes(row.status));
	let start = this_month();
	sent.forEach((row) => {
		const next = moment(row.payroll_date).add(1, "month").startOf("month").format("YYYY-MM-DD");
		if (next > start) start = next;
	});
	frappe.prompt(
		{
			fieldname: "start",
			fieldtype: "Date",
			label: __("Start the Remaining Installments From"),
			reqd: 1,
			default: start,
			description: __("The installments not deducted, the missed ones first, one a month from this month."),
		},
		(values) => call(frm, "move_remaining", values),
		__("Move Remaining Installments"),
		__("Move Installments")
	);
}

function postpone(frm) {
	const options = (frm.doc[SCHEDULE] || [])
		.filter((row) => row.status !== "Deducted")
		.map((row) => ({
			value: row.name,
			label: `${month_label(row.payroll_date)} — ${format_currency(row.amount, frm.doc.currency)} (${__(row.status)})`,
		}));
	frappe.prompt(
		{
			fieldname: "row",
			fieldtype: "Select",
			label: __("Installment"),
			reqd: 1,
			options,
			default: options[0]?.value,
			description: __("Moved to the month after the last installment."),
		},
		(values) => call(frm, "postpone", values),
		__("Postpone an Installment"),
		__("Postpone Installment")
	);
}
