const EVALUATION = "ms_hrms.custom_hrms.doctype.employee_evaluation.employee_evaluation";
const STATUS_MANAGER = "بانتظار تقييم المدير";
const STATUS_HR = "بانتظار الموارد البشرية";
const BY_MANAGER = "مدير الموظف";

frappe.ui.form.on("Employee Evaluation", {
	setup(frm) {
		frm.set_query("template", () => ({ filters: { disabled: 0 } }));
	},
	refresh(frm) {
		// Actions first: they clear Frappe's "submit" note, which shares the intro's place.
		frm.events.add_actions(frm);
		frm.events.show_intro(frm);
		render_evaluation(frm);
	},
	show_intro(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		if (frm.doc.status === STATUS_MANAGER) {
			frm.set_intro(
				frm.doc.evaluator_user
					? __("بانتظار تقييم {0} لأجزائه.", [frm.doc.evaluator_name || frm.doc.evaluator])
					: __("حدد المقيِّم: الموظف ليس له مدير في «يتبع» (Reports To)."),
				frm.doc.evaluator_user ? "blue" : "orange"
			);
		} else if (frm.doc.status === STATUS_HR) {
			frm.set_intro(__("بانتظار الموارد البشرية لتقييم أجزائها واعتماد التقييم."), "blue");
		}
	},
	add_actions(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		// Submitting waits for the manager; the manager sends instead.
		if (frm.doc.status === STATUS_MANAGER && !frm.is_dirty()) {
			frm.page.clear_primary_action();
			frm.dashboard.clear_comment();
			if (frm.doc.evaluator_user === frappe.session.user) {
				frm.page.set_primary_action(__("إرسال للموارد البشرية"), () => send_to_hr(frm));
			}
		}
		if (frm.doc.status === STATUS_HR && is_hr()) {
			frm.add_custom_button(__("إرجاع للمدير"), () => return_to_manager(frm));
		}
	},
	employee(frm) {
		if (!frm.doc.employee) return;
		frappe.call(`${EVALUATION}.get_template`, { employee: frm.doc.employee }).then((r) => {
			frm.set_value("template", r.message || null);
			if (!r.message) frappe.msgprint(__("لا يوجد قالب تقييم لهذا الموظف."));
		});
		frappe.db.get_value("Employee", frm.doc.employee, "reports_to").then((r) => {
			frm.set_value("evaluator", r.message?.reports_to || null);
		});
	},
});

function is_hr() {
	return frappe.user.has_role(["HR Manager", "HR User", "System Manager"]);
}

function can_score(frm, evaluated_by) {
	if (frm.doc.docstatus !== 0 || frm.is_new()) return false;
	if (evaluated_by === BY_MANAGER) {
		return frm.doc.status === STATUS_MANAGER && frm.doc.evaluator_user === frappe.session.user;
	}
	return is_hr();
}

// The items, part by part, with the scores open to whoever scores each part.
function render_evaluation(frm) {
	const wrapper = frm.get_field("evaluation_html").$wrapper;
	const esc = frappe.utils.escape_html;
	if (!(frm.doc.parts || []).length) {
		wrapper.html(
			`<p class="text-muted">${__("تظهر أجزاء التقييم وبنوده من القالب بعد الحفظ.")}</p>`
		);
		return;
	}

	const sections = frm.doc.parts.map((part, index) => {
		const editable = can_score(frm, part.evaluated_by);
		const rows = (frm.doc.items || [])
			.filter((row) => row.part === part.part_name)
			.map(
				(row) => `
				<tr>
					<td>${esc(row.kra)}</td>
					<td class="text-muted">${format_percent(row.weight)}</td>
					<td>${
						editable
							? `<div class="ev-score-cell">
								<input type="number" min="0" max="${flt(row.weight)}" step="any"
									class="form-control input-xs ev-score" data-row="${esc(row.name)}"
									data-max="${flt(row.weight)}" value="${flt(row.score)}">
								<span class="text-muted" dir="ltr">/ ${flt(row.weight, 2)}</span>
							</div>`
							: `<b dir="ltr">${format_out_of(row.score, row.weight)}</b>`
					}</td>
					<td>${
						editable
							? `<input type="text" class="form-control input-xs ev-notes" data-row="${esc(row.name)}"
								value="${esc(row.notes || "")}">`
							: esc(row.notes || "")
					}</td>
				</tr>`
			)
			.join("");
		return `
			<div class="ev-part">
				<div class="ev-part-head">
					<div>
						<span class="ev-part-index">${index + 1}</span>
						<b>${esc(part.part_name)}</b>
						<span class="text-muted"> — ${__("الوزن")} ${format_percent(part.weight)}
							— ${__("يقيّمه")} ${esc(part.evaluated_by)}</span>
					</div>
					<div>${__("النتيجة")}: <b class="ev-part-score" dir="ltr" data-part="${esc(part.part_name)}">${format_out_of(
						part.score,
						part.weight
					)}</b></div>
				</div>
				${
					// Rich text from the template, sanitized by Frappe when the template was saved.
					strip_html(part.notes || "").trim() || (part.notes || "").includes("<img")
						? `<div class="ev-part-notes">${part.notes}</div>`
						: ""
				}
				<table class="table table-bordered ev-table">
					<thead><tr>
						<th style="width: 40%">${__("البند")}</th>
						<th style="width: 10%">${__("الوزن")}</th>
						<th style="width: 15%">${__("الدرجة من الوزن")}</th>
						<th>${__("ملاحظات")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`;
	});

	wrapper.html(`
		<style>
			.ev-part { margin-bottom: var(--margin-lg); }
			.ev-part-head { display: flex; justify-content: space-between; align-items: center; gap: var(--margin-sm);
				flex-wrap: wrap; padding: var(--padding-sm) var(--padding-md); background: var(--subtle-fg);
				border: 1px solid var(--border-color); border-bottom: 0; border-radius: var(--border-radius) var(--border-radius) 0 0; }
			.ev-part-index { display: inline-flex; width: 22px; height: 22px; align-items: center; justify-content: center;
				border-radius: 50%; background: var(--primary); color: var(--white); font-size: var(--text-xs); margin-inline-end: 6px; }
			.ev-part-notes { padding: var(--padding-sm) var(--padding-md); border: 1px solid var(--border-color);
				border-bottom: 0; background: var(--card-bg); overflow-x: auto; }
			.ev-part-notes p:last-child { margin-bottom: 0; }
			.ev-part-notes table { width: 100%; margin: 0; border-collapse: collapse; }
			.ev-part-notes td, .ev-part-notes th { border: 1px solid var(--border-color); padding: 6px 10px; text-align: center; }
			.ev-table { margin: 0; border-radius: 0 0 var(--border-radius) var(--border-radius); }
			.ev-table td, .ev-table th { vertical-align: middle; }
			.ev-score-cell { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
		</style>
		${sections.join("")}
	`);

	wrapper.find(".ev-score").on("change", function () {
		const max = flt(this.dataset.max);
		let value = flt(this.value);
		if (value > max) {
			frappe.show_alert({ message: __("أقصى درجة لهذا البند {0}.", [flt(max, 2)]), indicator: "orange" });
		}
		value = Math.min(max, Math.max(0, value));
		this.value = value;
		frappe.model.set_value("Employee Evaluation Item", this.dataset.row, "score", value);
		calculate(frm);
	});
	wrapper.find(".ev-notes").on("change", function () {
		frappe.model.set_value("Employee Evaluation Item", this.dataset.row, "notes", this.value);
	});
}

function format_percent(value) {
	return `${flt(value, 2)}%`;
}

function format_out_of(value, max) {
	return `${flt(value, 2)} / ${flt(max, 2)}`;
}

// The scores as the server calculates them, shown while scoring: an item out of its weight,
// a part out of its weight, and the final score the parts' sum.
function calculate(frm) {
	let final = 0;
	for (const part of frm.doc.parts || []) {
		const total = (frm.doc.items || [])
			.filter((row) => row.part === part.part_name)
			.reduce((sum, row) => sum + flt(row.score), 0);
		part.score = flt((total * flt(part.weight)) / 100, 2);
		final += part.score;
		frm.get_field("evaluation_html")
			.$wrapper.find(`.ev-part-score[data-part="${CSS.escape(part.part_name)}"]`)
			.text(format_out_of(part.score, part.weight));
	}
	frm.doc.final_score = flt(final, 2);
	frm.doc.incentive_amount = flt((flt(frm.doc.incentive_base) * frm.doc.final_score) / 100, 2);
	frm.refresh_fields(["parts", "final_score", "incentive_amount"]);
}

function unscored(frm) {
	return (frm.doc.items || [])
		.filter((row) => row.evaluated_by === BY_MANAGER && !flt(row.score))
		.map((row) => row.kra);
}

async function send_to_hr(frm) {
	if (frm.is_dirty()) await frm.save();
	const send = () =>
		frappe.call(`${EVALUATION}.send_to_hr`, { name: frm.doc.name }).then(() => frm.reload_doc());
	const zero = unscored(frm);
	frappe.confirm(
		zero.length
			? __("هذه البنود درجتها صفر:<br>{0}<br><br>إرسال التقييم للموارد البشرية؟", [
					zero.map((kra) => frappe.utils.escape_html(kra)).join("<br>"),
			  ])
			: __("بعد الإرسال لا يمكنك تعديل تقييمك إلا إذا أرجعته الموارد البشرية. إرسال؟"),
		send
	);
}

function return_to_manager(frm) {
	frappe.prompt(
		{ fieldname: "reason", fieldtype: "Small Text", label: __("سبب الإرجاع"), reqd: 1 },
		({ reason }) =>
			frappe
				.call(`${EVALUATION}.return_to_manager`, { name: frm.doc.name, reason })
				.then(() => frm.reload_doc()),
		__("إرجاع التقييم للمدير"),
		__("إرجاع")
	);
}
