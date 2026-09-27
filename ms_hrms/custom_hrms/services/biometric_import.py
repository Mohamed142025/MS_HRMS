"""Importing the biometric device's sheet into Employee Checkin.

The sheet is uploaded as the device exports it (Excel or CSV): the device code and the date and
time of each punch. The employee is the one whose Attendance Device ID is that code. The punches
of codes not set on any employee stay on the import, to be imported once HR sets the code on the
employee, or ignored.

IN and OUT: the punches of one employee in one shift (the shift window HRMS itself gives the
checkin) are put in order; the first is IN, the last is OUT, and those in between alternate. A
single punch is IN or OUT by whether it is nearer the start or the end of the shift. Without a
shift, the day is the group (the checkin keeps no shift, as in HRMS), and a single punch is IN
before noon and OUT after. A punch within two minutes of the one before is the device repeating
itself and is dropped. Checkins made by an earlier import are given their type again when new
punches join their group; other checkins are left as they are.

After the import, the last sync of every shift that got checkins moves up to cover them and
HRMS's auto attendance runs, so a day without punches is an absence. When punches arrive for a
day already marked absent (no leave), that absence is cancelled first, if the user confirms.
"""

import json
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

DRAFT, RUNNING, DONE, WAITING = "مسودة", "جاري الاستيراد", "تم الاستيراد", "مستني أكواد"
CODE_WAITING, CODE_IMPORTED, CODE_IGNORED = "مستني", "اترفع", "متجاهل"
MONTH_FIRST, DAY_FIRST, AUTO = "شهر/يوم/سنة", "يوم/شهر/سنة", "تلقائي"
REPEAT_WINDOW = timedelta(minutes=2)
NOON = time(12, 0)
LIST_LIMIT = 60

CODE_HEADERS = {
	"no.", "no", "ac-no.", "ac-no", "acno", "ac no", "id", "user id", "userid", "user no", "enroll no", "enrollno",
	"enroll id", "emp no", "empno", "emp id", "code", "badge", "pin", "person id", "كود", "الكود", "كود البصمة", "رقم", "الرقم",
}
DATETIME_HEADERS = {
	"date/time", "datetime", "date time", "date & time", "timestamp", "time stamp", "checktime", "check time",
	"punch time", "التاريخ والوقت", "التاريخ/الوقت", "الوقت والتاريخ",
}
DATE_HEADERS = {"date", "التاريخ", "اليوم"}
TIME_HEADERS = {"time", "الوقت", "الساعة"}
DATE_PATTERN = re.compile(
	r"^\s*(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})"
	r"(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp]\.?\s*[Mm]\.?|ص|م)?)?\s*$"
)
TIME_PATTERN = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp]\.?\s*[Mm]\.?|ص|م)?\s*$")


# Reading the sheet ------------------------------------------------------------------------


def read_sheet(file_url):
	file = frappe.get_doc("File", {"file_url": file_url})
	extension = (file.file_name or file_url).rsplit(".", 1)[-1].lower()
	content = file.get_content()
	if extension == "xlsx":
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		return read_xlsx_file_from_attached_file(fcontent=content)
	if extension == "xls":
		import xlrd

		book = xlrd.open_workbook(file_contents=content)
		sheet = book.sheet_by_index(0)
		return [
			[
				xlrd.xldate_as_datetime(cell.value, book.datemode) if cell.ctype == xlrd.XL_CELL_DATE else cell.value
				for cell in sheet.row(r)
			]
			for r in range(sheet.nrows)
		]
	if extension == "csv":
		from frappe.utils.csvutils import read_csv_content

		return read_csv_content(content)
	frappe.throw(_("الملف لازم يبقى Excel (xlsx أو xls) أو CSV."))


def _label(value):
	return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def find_columns(rows):
	"""The header row and the columns of the code and of the date and time (together, or apart)."""
	for index, row in enumerate(rows[:15]):
		labels = [_label(v) for v in row]
		code = next((i for i, v in enumerate(labels) if v in CODE_HEADERS), None)
		when = next((i for i, v in enumerate(labels) if v in DATETIME_HEADERS), None)
		day = next((i for i, v in enumerate(labels) if v in DATE_HEADERS), None)
		clock = next((i for i, v in enumerate(labels) if v in TIME_HEADERS), None)
		if code is None or (when is None and day is None and clock is None):
			continue
		if when is None and day is not None and clock is not None:
			return {"header": index, "code": code, "date": day, "time": clock, "labels": row}
		return {"header": index, "code": code, "when": when if when is not None else (day if day is not None else clock), "labels": row}
	# No header: the device's usual order, the code then the date and time.
	return {"header": -1, "code": 0, "when": 1, "labels": None}


def _code(value):
	if isinstance(value, float) and value.is_integer():
		value = int(value)
	return str(value if value is not None else "").strip()


def _clock(hour, minute, second, meridiem):
	hour, minute, second = int(hour), int(minute), int(second or 0)
	meridiem = (meridiem or "").replace(".", "").replace(" ", "").lower()
	if meridiem in ("pm", "م") and hour < 12:
		hour += 12
	elif meridiem in ("am", "ص") and hour == 12:
		hour = 0
	return time(hour, minute, second)


def _time_of(value):
	if isinstance(value, datetime):
		return value.time().replace(microsecond=0)
	if isinstance(value, time):
		return value.replace(microsecond=0)
	if isinstance(value, timedelta):
		return (datetime.min + value).time()
	if isinstance(value, float | int) and 0 <= value < 1:  # a fraction of a day (Excel)
		return (datetime.min + timedelta(seconds=round(value * 86400))).time()
	match = TIME_PATTERN.match(str(value or ""))
	return _clock(*match.groups()) if match else None


class Reading:
	"""The punches of a sheet: (code, datetime), plus what could not be read."""

	def __init__(self, rows, columns, date_order):
		self.columns = columns
		self.date_order = date_order
		self.punches = []
		self.unreadable = []
		self.ambiguous = False
		self.order_used = None
		self._read(rows)

	def _raw(self, row):
		c = self.columns
		cell = lambda i: row[i] if i is not None and i < len(row) else None  # noqa: E731
		if "date" in c:
			return cell(c["code"]), (cell(c["date"]), cell(c["time"]))
		return cell(c["code"]), cell(c["when"])

	def _read(self, rows):
		pending, firsts, seconds = [], [], []
		for number, row in enumerate(rows[self.columns["header"] + 1 :], start=self.columns["header"] + 2):
			if not row or not any(str(v).strip() for v in row if v is not None):
				continue
			code, value = self._raw(row)
			code = _code(code)
			if not code:
				self.unreadable.append(number)
				continue
			pending.append((number, code, value))
			text = value[0] if isinstance(value, tuple) else value
			if isinstance(text, str):
				match = DATE_PATTERN.match(text)
				if match and len(match.group(1)) < 4:
					firsts.append(int(match.group(1)))
					seconds.append(int(match.group(2)))

		day_first = self._decide_order(firsts, seconds)
		for number, code, value in pending:
			moment = self._moment(value, day_first)
			if moment:
				self.punches.append((code, moment))
			else:
				self.unreadable.append(number)

	def _decide_order(self, firsts, seconds):
		if self.date_order == DAY_FIRST:
			self.order_used = DAY_FIRST
			return True
		if self.date_order == MONTH_FIRST:
			self.order_used = MONTH_FIRST
			return False
		day_first = any(v > 12 for v in firsts)
		month_first = any(v > 12 for v in seconds)
		if day_first and month_first:
			frappe.throw(_("التواريخ في الملف مش على شكل واحد (فيها يوم/شهر وشهر/يوم). حدد «ترتيب التاريخ» يدوي."))
		self.ambiguous = bool(firsts) and not day_first and not month_first
		# The device's own export (8/26/2026 9:23 AM) is month first.
		self.order_used = DAY_FIRST if day_first else MONTH_FIRST
		return day_first

	def _moment(self, value, day_first):
		if isinstance(value, tuple):
			day, clock = value
			day = self._moment(day, day_first)
			clock = _time_of(clock)
			return datetime.combine(day.date(), clock) if day and clock else None
		if isinstance(value, datetime):
			return value.replace(microsecond=0, tzinfo=None)
		if isinstance(value, date):
			return datetime.combine(value, time())
		if isinstance(value, float | int) and 20000 < value < 80000:  # an Excel date serial
			return (datetime(1899, 12, 30) + timedelta(days=float(value))).replace(microsecond=0)
		match = DATE_PATTERN.match(str(value or ""))
		if not match:
			return None
		a, b, c, hour, minute, second, meridiem = match.groups()
		try:
			if len(a) == 4:
				year, month, day = int(a), int(b), int(c)
			else:
				year = int(c) + (2000 if len(c) <= 2 else 0)
				day, month = (int(a), int(b)) if day_first else (int(b), int(a))
			clock = _clock(hour, minute, second, meridiem) if hour is not None else time()
			return datetime.combine(date(year, month, day), clock)
		except ValueError:
			return None


# Planning ---------------------------------------------------------------------------------


def employees_for(codes):
	"""{code: employee row}, and the codes set on more than one employee."""
	found = defaultdict(list)
	for row in frappe.get_all(
		"Employee",
		filters={"attendance_device_id": ["in", list(codes)]},
		fields=["name", "employee_name", "attendance_device_id", "status"],
	):
		found[_code(row.attendance_device_id)].append(row)
	linked = {code: rows[0] for code, rows in found.items() if len(rows) == 1}
	shared = {code: rows for code, rows in found.items() if len(rows) > 1}
	return linked, shared


def log_types(times, shift):
	"""IN and OUT for the ordered punches of one group."""
	if len(times) == 1:
		moment = times[0]
		if shift:
			return ["IN" if abs(moment - shift.start_datetime) <= abs(shift.end_datetime - moment) else "OUT"]
		return ["IN" if moment.time() < NOON else "OUT"]
	return ["IN"] + ["OUT" if i % 2 else "IN" for i in range(1, len(times) - 1)] + ["OUT"]


class Plan:
	"""What importing a set of punches would do, worked out without saving anything."""

	def __init__(self, punches_by_employee, import_name=None):
		self.import_name = import_name
		self.create = []  # (employee, time, log_type)
		self.retype = []  # (checkin, log_type, fetch_shift)
		self.duplicates = 0
		self.collapsed = 0
		self.single = []  # (employee, when, log_type, has_shift)
		self.no_shift = defaultdict(set)  # employee -> {date}
		self.shift_ends = {}  # shift type -> latest actual end among the new checkins
		self.attendance_days = set()  # (employee, date) with new punches in a shift
		for employee, times in punches_by_employee.items():
			self._employee(employee, sorted(set(times)))

	def _employee(self, employee, times):
		from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift

		groups = {}
		for moment in times:
			shift = get_actual_start_end_datetime_of_shift(employee, moment, True)
			key = (shift.shift_type.name, shift.actual_start) if shift else (None, moment.date())
			groups.setdefault(key, {"shift": shift, "times": []})["times"].append(moment)
		for (_shift_name, anchor), group in groups.items():
			self._group(employee, group["shift"], anchor, group["times"])

	def _existing(self, employee, shift, anchor):
		if shift:
			filters = {"employee": employee, "time": ["between", [shift.actual_start, shift.actual_end]]}
		else:
			filters = {
				"employee": employee,
				"time": ["between", [datetime.combine(anchor, time()), datetime.combine(anchor, time(23, 59, 59))]],
				"shift": ["is", "not set"],
			}
		return frappe.get_all(
			"Employee Checkin", filters=filters, fields=["name", "time", "log_type", "shift", "custom_biometric_import"], order_by="time"
		)

	def _group(self, employee, shift, anchor, times):
		existing = self._existing(employee, shift, anchor)
		taken = {get_datetime(row.time).replace(second=0) for row in existing}
		items = [{"time": get_datetime(r.time), "row": r} for r in existing]
		for moment in times:
			if moment.replace(second=0) in taken:
				self.duplicates += 1
				continue
			items.append({"time": moment, "row": None})
		items.sort(key=lambda i: i["time"])

		kept = []
		for item in items:
			if item["row"] is None and kept and item["time"] - kept[-1]["time"] < REPEAT_WINDOW:
				self.collapsed += 1
				continue
			kept.append(item)
		# Checkins of an earlier import made before the employee had this shift (or any): the
		# sheet uploaded again puts them on the shift the employee has now.
		shift_name = shift.shift_type.name if shift else None
		stale = {i["row"].name for i in kept if i["row"] and i["row"].custom_biometric_import and (i["row"].shift or None) != shift_name}
		if not any(i["row"] is None for i in kept) and not stale:
			return

		for item, log_type in zip(kept, log_types([i["time"] for i in kept], shift)):
			row = item["row"]
			if row is None:
				self.create.append((employee, item["time"], log_type))
			elif row.name in stale:
				self.retype.append((row.name, log_type, True))
			elif row.custom_biometric_import and row.log_type != log_type:
				self.retype.append((row.name, log_type, False))
		if len(kept) == 1:
			self.single.append((employee, kept[0]["time"], log_types([kept[0]["time"]], shift)[0], bool(shift)))
		if shift:
			name = shift.shift_type.name
			self.shift_ends[name] = max(self.shift_ends.get(name, shift.actual_end), shift.actual_end)
			self.attendance_days.add((employee, shift.start_datetime.date()))
		else:
			self.no_shift[employee].add(anchor)

	def absences(self):
		"""Absences (not leave) on the days that get punches now."""
		if not self.attendance_days:
			return []
		employees = {e for e, _d in self.attendance_days}
		rows = frappe.get_all(
			"Attendance",
			filters={
				"docstatus": 1,
				"status": "Absent",
				"employee": ["in", list(employees)],
				"attendance_date": ["in", list({d for _e, d in self.attendance_days})],
			},
			fields=["name", "employee", "employee_name", "attendance_date", "leave_type", "leave_application"],
		)
		return [r for r in rows if (r.employee, getdate(r.attendance_date)) in self.attendance_days and not r.leave_type and not r.leave_application]

	def sync_changes(self):
		"""Per shift: the last sync now, after, and from where attendance will be worked out."""
		changes = []
		for shift_name, actual_end in sorted(self.shift_ends.items()):
			shift = frappe.db.get_value(
				"Shift Type", shift_name, ["last_sync_of_checkin", "process_attendance_after", "enable_auto_attendance"], as_dict=True
			)
			new_sync = actual_end + timedelta(minutes=1)
			current = get_datetime(shift.last_sync_of_checkin) if shift.last_sync_of_checkin else None
			changes.append(
				frappe._dict(
					shift=shift_name,
					current=current,
					new=max(current, new_sync) if current else new_sync,
					moves=not current or new_sync > current,
					from_date=getdate(current) if current else getdate(shift.process_attendance_after) if shift.process_attendance_after else None,
					auto=bool(shift.enable_auto_attendance and shift.process_attendance_after),
				)
			)
		return changes


# Reading an import ---------------------------------------------------------------------------


def read_import(doc):
	rows = read_sheet(doc.import_file)
	if not rows:
		frappe.throw(_("الملف فاضي."))
	columns = find_columns(rows)
	reading = Reading(rows, columns, doc.date_order or AUTO)
	if not reading.punches:
		frappe.throw(_("مفيش بصمات اتقرت من الملف. اتأكد إن فيه عمود للكود وعمود للتاريخ والوقت."))
	labels = columns.get("labels") or []
	name = lambda i: str(labels[i]) if labels and i is not None and i < len(labels) else f"العمود {i + 1}"  # noqa: E731
	doc.code_column = name(columns["code"])
	doc.time_column = f"{name(columns['date'])} + {name(columns['time'])}" if "date" in columns else name(columns["when"])
	return reading


def split_punches(punches):
	"""The punches of linked codes by employee; the rest by code."""
	linked, shared = employees_for({code for code, _t in punches})
	by_employee, unlinked, inactive = defaultdict(list), defaultdict(list), defaultdict(int)
	for code, moment in punches:
		employee = linked.get(code)
		if not employee:
			unlinked[code].append(moment)
		elif employee.status != "Active":
			inactive[(code, employee.name, employee.employee_name)] += 1
		else:
			by_employee[employee.name].append(moment)
	return by_employee, unlinked, shared, inactive, linked


def preview(doc):
	reading = read_import(doc)
	by_employee, unlinked, shared, inactive, linked = split_punches(reading.punches)
	plan = Plan(by_employee, doc.name)
	names = _names(set(by_employee) | {e for e, _t, _l, _s in plan.single} | set(plan.no_shift))
	times = [t for _c, t in reading.punches]
	return {
		"order": reading.order_used,
		"ambiguous": reading.ambiguous,
		"code_column": doc.code_column,
		"time_column": doc.time_column,
		"total": len(reading.punches),
		"unreadable": reading.unreadable[:20],
		"unreadable_count": len(reading.unreadable),
		"from": min(times),
		"to": max(times),
		"employees": [
			{"employee": e, "employee_name": names.get(e), "punches": len(t)} for e, t in sorted(by_employee.items(), key=lambda x: names.get(x[0]) or "")
		],
		"unlinked": _code_rows(unlinked),
		"shared": [{"code": c, "employees": ", ".join(r.employee_name for r in rows)} for c, rows in shared.items()],
		"inactive": [{"code": c, "employee_name": n, "punches": count} for (c, _e, n), count in inactive.items()],
		"create": len(plan.create),
		"retype": len(plan.retype),
		"reshift": sum(1 for r in plan.retype if r[2]),
		"duplicates": plan.duplicates,
		"collapsed": plan.collapsed,
		"single": [
			{"employee_name": names.get(e), "time": t, "log_type": lt, "shift": s}
			for e, t, lt, s in sorted(plan.single, key=lambda x: x[1])[:LIST_LIMIT]
		],
		"single_count": len(plan.single),
		"no_shift": [
			{"employee_name": names.get(e), "days": len(days), "from": min(days), "to": max(days)} for e, days in plan.no_shift.items()
		],
		"sync": plan.sync_changes(),
		"absences": [
			{"employee_name": a.employee_name, "date": a.attendance_date, "attendance": a.name} for a in plan.absences()
		],
	}


def _names(employees):
	if not employees:
		return {}
	return dict(frappe.get_all("Employee", filters={"name": ["in", list(employees)]}, fields=["name", "employee_name"], as_list=True))


def _code_rows(unlinked):
	return [
		{"code": code, "punches": len(times), "first": min(times), "last": max(times)}
		for code, times in sorted(unlinked.items(), key=lambda x: (len(x[0]), x[0]))
	]


# Running an import ---------------------------------------------------------------------------


def run(doc, correct_absences=False):
	"""Import the sheet: every linked code now, the others kept on the import."""
	reading = read_import(doc)
	# A code set on more than one employee is not linked, and waits with the others.
	by_employee, unlinked, shared, inactive, _linked = split_punches(reading.punches)
	times = [t for _c, t in reading.punches]
	doc.from_time, doc.to_time, doc.total_punches = min(times), max(times), len(reading.punches)
	log = [_("قراءة الملف: {0} بصمة من {1} لـ {2} (التاريخ {3}).").format(len(reading.punches), doc.from_time, doc.to_time, reading.order_used)]
	if reading.unreadable:
		log.append(_("سطور ما اتقرتش: {0}").format(", ".join(map(str, reading.unreadable[:50]))))
	for (code, _employee, name), count in inactive.items():
		log.append(_("الكود {0}: {1} مش نشط، {2} بصمة ما اترفعتش.").format(code, name, count))
	for code, rows in shared.items():
		log.append(_("الكود {0} متسجل على أكتر من موظف ({1})، بصماته مستنية.").format(code, ", ".join(r.name for r in rows)))

	result = import_punches(doc, by_employee, correct_absences, log)
	doc.pending_rows = json.dumps([[c, str(t)] for c, ts in unlinked.items() for t in ts])
	doc.set("codes", [])
	for row in _code_rows(unlinked):
		doc.append("codes", {"device_code": row["code"], "punches": row["punches"], "first_punch": row["first"], "last_punch": row["last"], "code_status": CODE_WAITING})
	if unlinked:
		log.append(_("أكواد مش مربوطة بموظف ({0}): {1}. بصماتها مستنية «إعادة رفع اللي ما اترفعش».").format(len(unlinked), ", ".join(sorted(unlinked))))
	_finish(doc, result, log, first=True)
	return result


def retry(doc, correct_absences=False):
	"""Import the waiting punches whose codes are now set on an employee."""
	waiting = defaultdict(list)
	for code, moment in json.loads(doc.pending_rows or "[]"):
		waiting[code].append(get_datetime(moment))
	linked, _shared = employees_for(set(waiting))
	by_employee, log, done = defaultdict(list), [], set()
	for code, employee in linked.items():
		if employee.status != "Active":
			continue
		by_employee[employee.name].extend(waiting[code])
		done.add(code)
		for row in doc.codes:
			if row.device_code == code:
				row.code_status, row.employee, row.employee_name = CODE_IMPORTED, employee.name, employee.employee_name
		log.append(_("الكود {0} ← {1} ({2}): {3} بصمة.").format(code, employee.name, employee.employee_name, len(waiting[code])))
	if not done:
		frappe.throw(_("لسه مفيش كود من الأكواد المستنية متحط على موظف. حط الكود في «Attendance Device ID» في ملف الموظف الأول."))
	result = import_punches(doc, by_employee, correct_absences, log)
	doc.pending_rows = json.dumps([[c, str(t)] for c, ts in waiting.items() if c not in done for t in ts])
	_finish(doc, result, log, first=False)
	return result


def retry_preview(doc):
	waiting = defaultdict(list)
	for code, moment in json.loads(doc.pending_rows or "[]"):
		waiting[code].append(get_datetime(moment))
	linked, _shared = employees_for(set(waiting))
	ready = {code: e for code, e in linked.items() if e.status == "Active"}
	plan = Plan({e.name: waiting[code] for code, e in ready.items()}, doc.name)
	return {
		"ready": [{"code": c, "employee": e.name, "employee_name": e.employee_name, "punches": len(waiting[c])} for c, e in sorted(ready.items())],
		"still": sorted(c for c in waiting if c not in ready),
		"create": len(plan.create),
		"absences": [{"employee_name": a.employee_name, "date": a.attendance_date, "attendance": a.name} for a in plan.absences()],
		"sync": plan.sync_changes(),
	}


def ignore_codes(doc, codes):
	codes = set(codes or [])
	rows = [[c, t] for c, t in json.loads(doc.pending_rows or "[]") if c not in codes]
	doc.pending_rows = json.dumps(rows)
	for row in doc.codes:
		if row.device_code in codes and row.code_status == CODE_WAITING:
			row.code_status = CODE_IGNORED
	doc.pending = len(rows)
	doc.status = WAITING if rows else DONE
	doc.import_log = "\n".join(filter(None, [doc.import_log, _("{0}: تجاهل الأكواد {1}.").format(now_datetime().replace(microsecond=0), ", ".join(sorted(codes)))]))


def import_punches(doc, by_employee, correct_absences, log):
	plan = Plan(by_employee, doc.name)
	absences = plan.absences()
	corrected = 0
	if absences and correct_absences:
		for row in absences:
			attendance = frappe.get_doc("Attendance", row.name)
			attendance.flags.ignore_permissions = True
			attendance.cancel()
			corrected += 1
		log.append(_("غياب اتلغى لأن اليوم بقى فيه بصمات: {0}.").format(", ".join(f"{a.employee_name} {a.attendance_date}" for a in absences)))
	elif absences:
		log.append(_("أيام متسجل عليها غياب وبقى فيها بصمات (ما اتصححتش): {0}.").format(len(absences)))

	for employee, moment, log_type in plan.create:
		frappe.get_doc(
			{"doctype": "Employee Checkin", "employee": employee, "time": moment, "log_type": log_type, "custom_biometric_import": doc.name}
		).insert(ignore_permissions=True)
	reshifted = 0
	for name, log_type, fetch_shift in plan.retype:
		if fetch_shift:
			checkin = frappe.get_doc("Employee Checkin", name)
			checkin.log_type = log_type
			checkin.save(ignore_permissions=True)  # fetches the shift the employee has now
			reshifted += 1
		else:
			frappe.db.set_value("Employee Checkin", name, "log_type", log_type)
	log.append(
		_("اترفع {0} بصمة لـ {1} موظف. موجود قبل كده: {2}. مكرر خلال دقيقتين: {3}. نوع اتعدّل في بصمات سابقة: {4}.").format(
			len(plan.create), len(by_employee), plan.duplicates, plan.collapsed, len(plan.retype) - reshifted
		)
	)
	if reshifted:
		log.append(_("بصمات سابقة اتربطت بالوردية الحالية للموظف: {0}.").format(reshifted))
	no_shift_days = sum(len(d) for d in plan.no_shift.values())
	if no_shift_days:
		log.append(_("أيام من غير وردية (البصمات من غير وردية والحضور ما اتحسبش): {0} يوم لـ {1} موظف.").format(no_shift_days, len(plan.no_shift)))
	log.extend(_mark_attendance(plan))
	return frappe._dict(created=len(plan.create), duplicates=plan.duplicates, collapsed=plan.collapsed, corrected=corrected)


def _mark_attendance(plan):
	lines = []
	for change in plan.sync_changes():
		shift = frappe.get_doc("Shift Type", change.shift)
		if change.moves:
			shift.db_set("last_sync_of_checkin", change.new, update_modified=False)
		if not change.auto:
			lines.append(_("الوردية {0}: الحضور التلقائي مش متظبط (Process Attendance After)، فالحضور ما اتحسبش.").format(change.shift))
			continue
		shift.reload()
		shift.process_auto_attendance()
		lines.append(_("الوردية {0}: آخر مزامنة {1}، والحضور اتحسب من {2}.").format(change.shift, change.new, change.from_date))
	return lines


def _finish(doc, result, log, first):
	stamp = now_datetime().replace(microsecond=0)
	doc.imported = cint(doc.imported) + result.created
	doc.duplicates = cint(doc.duplicates) + result.duplicates
	doc.collapsed = cint(doc.collapsed) + result.collapsed
	doc.absents_corrected = cint(doc.absents_corrected) + result.corrected
	doc.pending = len(json.loads(doc.pending_rows or "[]"))
	doc.status = WAITING if doc.pending else DONE
	if first:
		doc.imported_by, doc.imported_on = frappe.session.user, stamp
	title = _("الاستيراد") if first else _("إعادة رفع اللي ما اترفعش")
	doc.import_log = "\n".join(filter(None, [doc.import_log, f"— {stamp} · {title} ({frappe.session.user})", *log]))
