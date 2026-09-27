// Biometric Import: upload the device's sheet, check the preview, import. Codes not set on an
// employee wait on the import until HR sets them, then «إعادة رفع اللي ما اترفعش».
(() => {
	const DRAFT = "مسودة";
	const RUNNING = "جاري الاستيراد";
	const WAITING = "مستني أكواد";
	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
	const when = (v) => (v ? frappe.datetime.str_to_user(v) : "");
	const day = (v) => (v ? frappe.datetime.str_to_user(String(v).slice(0, 10)) : "");

	frappe.ui.form.on("Biometric Import", {
		setup(frm) {
			frappe.realtime.on("biometric_import_done", (data) => {
				if (data.name !== frm.doc.name) return;
				frm.reload_doc();
				frappe.show_alert({ message: data.error ? __("الاستيراد وقف بخطأ، شوف Error Log.") : __("خلص الاستيراد."), indicator: data.error ? "red" : "green" });
			});
		},

		refresh(frm) {
			// Connections list the checkins this import made; they are not added by hand from here.
			frm.can_make_methods = { ...frm.can_make_methods, "Employee Checkin": () => false };
			frm.set_df_property("import_file", "read_only", frm.doc.status !== DRAFT);
			frm.set_df_property("date_order", "read_only", frm.doc.status !== DRAFT);
			if (frm.doc.status !== DRAFT) frm.disable_save();
			if (frm.doc.status === RUNNING) {
				frm.dashboard.set_headline(__("جاري الاستيراد في الخلفية… الصفحة هتتحدث لما يخلص."));
			}
			if (frm.doc.status === DRAFT && !frm.is_new() && frm.doc.import_file) {
				load_preview(frm);
			} else if (frm.doc.status === DRAFT) {
				frm.get_field("preview_html").$wrapper.html("");
			}
			if (frm.doc.status === WAITING) {
				frm.add_custom_button(__("إعادة رفع اللي ما اترفعش"), () => retry(frm)).addClass("btn-primary");
				frm.add_custom_button(__("تجاهل أكواد"), () => ignore(frm));
			}
		},

		import_file(frm) {
			if (frm.doc.import_file && frm.doc.status === DRAFT) frm.save();
		},
		date_order(frm) {
			if (frm.doc.import_file && !frm.is_new()) frm.save();
		},
	});

	function load_preview(frm) {
		const wrapper = frm.get_field("preview_html").$wrapper;
		wrapper.html(`<p class="text-muted">${__("بنقرا الملف…")}</p>`);
		frm.call("get_preview")
			.then(({ message: p }) => {
				wrapper.html(render_preview(p));
				frm.page.set_primary_action(__("استيراد"), () => confirm_import(frm, p));
			})
			.catch(() => wrapper.html(`<p class="text-danger">${__("الملف ما اتقراش. اتأكد من الشيت.")}</p>`));
	}

	function card(label, value, tone = "") {
		return `<div class="col-6 col-md-3 mb-3"><div class="border rounded p-3 h-100 ${tone}">
			<div class="small text-muted">${label}</div><div class="h5 mb-0 mt-1">${value}</div></div></div>`;
	}

	function table(headers, rows) {
		if (!rows.length) return "";
		return `<table class="table table-sm table-bordered mt-2"><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
			<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
	}

	function render_preview(p) {
		const parts = [];
		parts.push(`<p class="mb-2">${__("الأعمدة")}: <b>${esc(p.code_column)}</b> ${__("للكود")}، <b>${esc(p.time_column)}</b> ${__("للتاريخ والوقت")}
			· ${__("التاريخ اتقرا")} <b>${esc(p.order)}</b>${p.ambiguous ? ` <span class="text-warning">(${__("كل التواريخ تنفع بالطريقتين، راجع الفترة")})</span>` : ""}</p>`);
		parts.push(`<div class="row">
			${card(__("الفترة"), `${esc(when(p.from))}<br><small>${__("لـ")} ${esc(when(p.to))}</small>`)}
			${card(__("بصمات الشيت"), p.total)}
			${card(__("هتترفع"), `${p.create} <small class="text-muted">(${p.employees.length} ${__("موظف")})</small>`, "border-success")}
			${card(__("موجود قبل كده / مكرر"), `${p.duplicates} / ${p.collapsed}`)}
		</div>`);
		if (p.reshift) {
			parts.push(`<div class="alert alert-success">${__("بصمات اترفعت قبل كده من غير وردية (أو على وردية تانية) هتتربط بالوردية الحالية للموظف ويتحسب لها الحضور")}: <b>${p.reshift}</b></div>`);
		}
		if (p.unreadable_count) {
			parts.push(`<div class="alert alert-warning">${__("سطور ما اتقرتش")}: ${p.unreadable_count} (${p.unreadable.join(", ")}…)</div>`);
		}
		if (p.unlinked.length) {
			parts.push(`<div class="alert alert-warning mb-1"><b>${__("أكواد مش مربوطة بموظف")}: ${p.unlinked.length}</b> — ${__(
				"بصماتها هتفضل مستنية على الاستيراد لحد ما الكود يتحط في «Attendance Device ID» في ملف الموظف، وبعدها «إعادة رفع اللي ما اترفعش»."
			)}</div>`);
			parts.push(table([__("الكود"), __("البصمات"), __("أول بصمة"), __("آخر بصمة")], p.unlinked.map((u) => [esc(u.code), u.punches, esc(when(u.first)), esc(when(u.last))])));
		}
		if (p.shared.length) {
			parts.push(`<div class="alert alert-danger">${__("أكواد متسجلة على أكتر من موظف (هتستنى لحد ما تتصلح)")}: ${p.shared.map((s) => `${esc(s.code)} (${esc(s.employees)})`).join("، ")}</div>`);
		}
		if (p.inactive.length) {
			parts.push(`<div class="alert alert-secondary">${__("موظفين مش نشطين (بصماتهم مش هتترفع)")}: ${p.inactive.map((s) => `${esc(s.employee_name)} (${s.punches})`).join("، ")}</div>`);
		}
		if (p.sync.length) {
			parts.push(`<h6 class="mt-3">${__("الحضور بعد الاستيراد")}</h6>`);
			parts.push(table(
				[__("الوردية"), __("آخر مزامنة دلوقتي"), __("بعد الاستيراد"), __("الحضور هيتحسب")],
				p.sync.map((s) => [
					esc(s.shift),
					esc(when(s.current) || "—"),
					esc(when(s.new)),
					s.auto ? `${__("من")} ${esc(day(s.from_date))} ${__("، واليوم اللي مفيهوش بصمات غياب")}` : `<span class="text-danger">${__("الحضور التلقائي مش متظبط للوردية دي")}</span>`,
				])
			));
		}
		if (p.no_shift.length) {
			parts.push(`<div class="alert alert-info mt-2">${__("موظفين ملهمش وردية في أيام من الشيت: البصمات هتترفع من غير وردية، والدخول والخروج على اليوم، والحضور مش هيتحسب للأيام دي.")}</div>`);
			parts.push(table([__("الموظف"), __("أيام من غير وردية"), __("من"), __("إلى")], p.no_shift.map((n) => [esc(n.employee_name), n.days, esc(day(n.from)), esc(day(n.to))])));
		}
		if (p.single.length) {
			parts.push(`<h6 class="mt-3">${__("أيام فيها بصمة واحدة")} (${p.single_count})</h6>`);
			parts.push(table([__("الموظف"), __("البصمة"), __("اتحسبت")], p.single.map((s) => [esc(s.employee_name), esc(when(s.time)), s.log_type === "IN" ? __("دخول") : __("خروج")])));
		}
		if (p.absences.length) {
			parts.push(`<div class="alert alert-warning mt-2">${__("أيام متسجل عليها غياب وبقى فيها بصمات")}: ${p.absences.length} — ${__("هتتسأل عنها قبل الاستيراد.")}</div>`);
		}
		return parts.join("");
	}

	function absence_field(absences) {
		if (!absences.length) return [];
		return [
			{ fieldtype: "HTML", fieldname: "absences_list", options: `<p>${__("الأيام دي متسجل عليها غياب (من غير إجازة) وبقى فيها بصمات:")}</p>
				${table([__("الموظف"), __("اليوم")], absences.map((a) => [esc(a.employee_name), esc(day(a.date))]))}` },
			{ fieldtype: "Check", fieldname: "correct_absences", default: 1, label: __("ألغي الغياب ده واحسب الحضور من البصمات") },
		];
	}

	function confirm_import(frm, p) {
		const dialog = new frappe.ui.Dialog({
			title: __("استيراد البصمة"),
			fields: [
				{ fieldtype: "HTML", fieldname: "summary", options: `<p>${__("هيترفع {0} بصمة لـ {1} موظف، ويتحسب الحضور للورديات اللي فيها بصمات.", [p.create, p.employees.length])}</p>
					${p.reshift ? `<p>${__("وهتتربط {0} بصمة سابقة بالوردية الحالية.", [p.reshift])}</p>` : ""}
					${p.unlinked.length ? `<p class="text-warning">${__("{0} كود مش مربوط، بصماته هتستنى.", [p.unlinked.length])}</p>` : ""}` },
				...absence_field(p.absences),
			],
			primary_action_label: __("استيراد"),
			primary_action(values) {
				dialog.hide();
				frm.call("start_import", { correct_absences: values.correct_absences ? 1 : 0 }).then(() => frm.reload_doc());
			},
		});
		dialog.show();
	}

	function retry(frm) {
		frm.call("get_retry_preview").then(({ message: r }) => {
			const ready = r.ready.length
				? table([__("الكود"), __("الموظف"), __("البصمات")], r.ready.map((x) => [esc(x.code), `${esc(x.employee)} · ${esc(x.employee_name)}`, x.punches]))
				: `<p class="text-danger">${__("لسه مفيش كود من المستنية اتحط على موظف.")}</p>`;
			const dialog = new frappe.ui.Dialog({
				title: __("إعادة رفع اللي ما اترفعش"),
				fields: [
					{ fieldtype: "HTML", fieldname: "ready", options: `${ready}${r.still.length ? `<p class="text-muted">${__("لسه مستني")}: ${r.still.map(esc).join("، ")}</p>` : ""}` },
					...absence_field(r.absences),
				],
				primary_action_label: __("رفع"),
				primary_action(values) {
					dialog.hide();
					frm.call("retry_pending", { correct_absences: values.correct_absences ? 1 : 0 }).then(() => frm.reload_doc());
				},
			});
			if (!r.ready.length) dialog.get_primary_btn().prop("disabled", true);
			dialog.show();
		});
	}

	function ignore(frm) {
		const waiting = (frm.doc.codes || []).filter((c) => c.code_status === "مستني").map((c) => c.device_code);
		frappe.prompt(
			[{ fieldname: "codes", fieldtype: "MultiSelectList", label: __("الأكواد"), reqd: 1,
				get_data: (txt) => waiting.filter((c) => !txt || c.includes(txt)).map((c) => ({ value: c, description: "" })) }],
			({ codes }) => frm.call("ignore_codes", { codes }).then(() => frm.reload_doc()),
			__("تجاهل أكواد (بصماتها مش هتترفع)"),
			__("تجاهل")
		);
	}
})();
