// Shift Assignment Tool: shifts by day of the week (ms_hrms.shift_by_weekday). With the
// box ticked, Assign Shift takes day ranges, each with its shift, a line under the table
// reads the week back, and the result names who was assigned and why anyone was not.
(() => {
	const METHOD = "assign_shifts_by_weekday";
	const DONE_EVENT = "ms_hrms_weekday_shifts_done";
	const WEEK = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

	const by_weekday = (frm) => frm.doc.action === "Assign Shift" && !!frm.doc.custom_shift_by_weekday;

	frappe.ui.form.on("Shift Assignment Tool", {
		refresh(frm) {
			render_summary(frm);
			frappe.realtime.off(DONE_EVENT);
			frappe.realtime.on(DONE_EVENT, (result) => show_result(frm, result));
		},

		custom_shift_by_weekday(frm) {
			if (by_weekday(frm) && frm.doc.shift_type) frm.set_value("shift_type", "");
			render_summary(frm);
			frm.trigger("set_primary_action");
			frm.trigger("get_employees");
		},

		// Runs after Frappe HR's own handler: in this mode the button assigns by weekday.
		set_primary_action(frm) {
			if (!by_weekday(frm)) return;
			frm.page.clear_primary_action();
			frm.page.set_primary_action(__("Assign Shift"), () => assign(frm));
		},

		// Frappe HR lists employees only once one shift type is chosen; here the table
		// stands in for it.
		get_employees(frm) {
			if (!by_weekday(frm)) return;
			if (!(frm.doc.start_date && frm.doc.end_date && (frm.doc.custom_weekday_shifts || []).length)) {
				return frm.events.render_employees_datatable(frm, []);
			}
			frm.call({
				method: "get_employees",
				args: { advanced_filters: frm.advanced_filters || [] },
				doc: frm.doc,
			}).then((r) => frm.events.render_employees_datatable(frm, r.message));
		},

		custom_weekday_shifts_remove(frm) {
			changed(frm);
		},
	});

	frappe.ui.form.on("Weekday Shift Range", {
		// One day is the usual start: "to" follows "from" until it is changed.
		from_day(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			if (row.from_day && (!row.to_day || WEEK.indexOf(row.to_day) < WEEK.indexOf(row.from_day))) {
				frappe.model.set_value(cdt, cdn, "to_day", row.from_day);
			}
			changed(frm);
		},
		to_day: changed,
		shift_type: changed,
	});

	function changed(frm) {
		render_summary(frm);
		frm.trigger("get_employees");
	}

	// The week read back from the table: "السبت–الأربعاء: Main · الخميس: Evening · الجمعة: بدون شيفت",
	// with any row problem said plainly.
	function render_summary(frm) {
		const field = frm.get_field("custom_weekday_summary");
		if (!field) return;
		if (!by_weekday(frm)) return field.$wrapper.empty();

		const { day_shifts, errors } = read_ranges(frm.doc.custom_weekday_shifts || []);
		const parts = [];
		let i = 0;
		while (i < WEEK.length) {
			const shift = day_shifts[WEEK[i]] || null;
			let j = i;
			while (j + 1 < WEEK.length && (day_shifts[WEEK[j + 1]] || null) === shift) j++;
			const days = i === j ? __(WEEK[i]) : `${__(WEEK[i])}–${__(WEEK[j])}`;
			parts.push(
				shift
					? `<span class="bold">${days}</span>: ${frappe.utils.escape_html(shift)}`
					: `<span class="bold">${days}</span>: <span class="text-muted">${__("بدون شيفت")}</span>`
			);
			i = j + 1;
		}
		const error_html = errors.length
			? `<div class="text-danger small" style="margin-top:6px">${errors.map(frappe.utils.escape_html).join("<br>")}</div>`
			: "";
		field.$wrapper.html(
			`<div class="small" style="padding:8px 12px;border:1px solid var(--border-color);border-radius:var(--border-radius-md);background:var(--subtle-fg)">
				${parts.join(" · ")}
				<div class="text-muted" style="margin-top:4px">${__("أيام قائمة عطلات كل موظف لا يُعيَّن لها شيفت.")}</div>
				${error_html}
			</div>`
		);
	}

	function read_ranges(rows) {
		const day_shifts = {};
		const day_rows = {};
		const errors = [];
		rows.forEach((row) => {
			if (!row.from_day || !row.to_day || !row.shift_type) return;
			const start = WEEK.indexOf(row.from_day);
			const end = WEEK.indexOf(row.to_day);
			if (start > end) {
				errors.push(
					__("السطر {0}: «من {1}» بعد «إلى {2}». الأسبوع يبدأ السبت؛ قسّم المدة على سطرين.", [
						row.idx,
						__(row.from_day),
						__(row.to_day),
					])
				);
				return;
			}
			WEEK.slice(start, end + 1).forEach((day) => {
				if (day in day_shifts) {
					errors.push(__("يوم {0} مكرر في السطرين {1} و{2}.", [__(day), day_rows[day], row.idx]));
				} else {
					day_shifts[day] = row.shift_type;
					day_rows[day] = row.idx;
				}
			});
		});
		return { day_shifts, errors };
	}

	function assign(frm) {
		const rows = frm.employees_datatable?.datamanager.data || [];
		const employees = (frm.employees_datatable?.rowmanager.getCheckedRows() || []).map((idx) => rows[idx].employee);
		const missing = [
			["company", __("Company")],
			["start_date", __("Start Date")],
			["end_date", __("End Date")],
		]
			.filter(([fieldname]) => !frm.doc[fieldname])
			.map(([, label]) => label);
		if (!(frm.doc.custom_weekday_shifts || []).length) missing.push(__("شيفتات أيام الأسبوع"));
		if (missing.length) {
			frappe.throw({
				title: __("Missing Fields"),
				message: __("أكمل الحقول التالية:") + `<ul><li>${missing.join("</li><li>")}</li></ul>`,
			});
		}
		const { errors } = read_ranges(frm.doc.custom_weekday_shifts);
		if (errors.length) frappe.throw(errors.join("<br>"));
		if (!employees.length) frappe.throw(__("اختر موظفاً واحداً على الأقل."));

		frappe.confirm(
			__("تعيين الشيفتات حسب أيام الأسبوع لـ {0} موظف من {1} إلى {2}؟", [
				employees.length,
				frappe.datetime.str_to_user(frm.doc.start_date),
				frappe.datetime.str_to_user(frm.doc.end_date),
			]),
			() =>
				frm.call({
					method: METHOD,
					doc: frm.doc,
					args: { employees },
					freeze: true,
					freeze_message: __("جاري تعيين الشيفتات..."),
				}).then((r) => {
					if (r.message && !r.message.queued) show_result(frm, r.message);
				})
		);
	}

	// Who was assigned (with their assignments) and who was not, with the reason.
	function show_result(frm, { success = [], failure = [] }) {
		const esc = frappe.utils.escape_html;
		let html = "";
		if (success.length) {
			html += `<p class="bold text-success">${__("تم التعيين لـ {0} موظف", [success.length])}</p><ul>`;
			success.forEach((row) => {
				const links = row.assignments.map((name) => frappe.utils.get_form_link("Shift Assignment", name, true)).join("، ");
				html += `<li>${esc(row.employee_name)} (${esc(row.employee)}): ${__("{0} تعيين", [row.assignments.length])} — ${links}</li>`;
			});
			html += "</ul>";
		}
		if (failure.length) {
			html += `<p class="bold text-danger" style="margin-top:12px">${__("لم يتم التعيين لـ {0} موظف", [failure.length])}</p><ul>`;
			// The reason comes from the server with its own links.
			failure.forEach((row) => {
				html += `<li><b>${esc(row.employee_name)}</b> (${esc(row.employee)}): ${row.reason}</li>`;
			});
			html += "</ul>";
		}
		frappe.msgprint({
			title: failure.length ? __("نتيجة تعيين الشيفتات") : __("تم تعيين الشيفتات"),
			indicator: failure.length ? (success.length ? "orange" : "red") : "green",
			message: html || __("لم يُعالج أي موظف."),
			wide: true,
		});
		if (success.length) frm.trigger("get_employees");
	}
})();
