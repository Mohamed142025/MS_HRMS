"""Words the employee app (ms_hrms.pwa) shows that no app translates.

The app's request forms show the fields of Frappe HR's doctypes, translating their
labels in the browser (__(field.label)), and the request sheets take their labels from
plain lists (frontend/src/data/config). Frappe HR leaves some of them untranslated in
Arabic ("Dates & Reason", "Leave Approver" on the leave form), so they are listed here
to be extracted into ms_hrms' own translations (locale/), which override Frappe HR's.
Nothing calls this module.
"""

from frappe import N_

LABELS = (
	# Leave Application
	N_("Dates & Reason"),
	N_("Leave Approver"),
	N_("Other Details"),
	N_("Leave Dates"),
	N_("Select Leave Approver"),
	# Expense Claim and its tables
	N_("From Employee"),
	N_("Expense Approver"),
	N_("Exchange Rate"),
	N_("Advances"),
	N_("Total Sanctioned Amount (Company Currency)"),
	N_("Total Advance Amount (Company Currency)"),
	N_("Total Claimed Amount (Company Currency)"),
	N_("Total Taxes and Charges"),
	N_("Total Exchange Gain/Loss"),
	N_("Gain Loss Account"),
	N_("Accounting Details"),
	N_("Is Paid"),
	N_("Default Account"),
	N_("Sanctioned Amount"),
	N_("Sanctioned Amount (Company Currency)"),
	N_("Account Head"),
	# Employee Advance
	N_("Purpose & Amount"),
	N_("Number of Months"),
	N_("First Repayment Month"),
	N_("Monthly Installment"),
	N_("Missed Installments"),
	N_("Advance Account"),
	N_("Repay Unclaimed Amount from Salary"),
	# Attendance and shifts
	N_("Include Holidays"),
	N_("Attendance Dates"),
	N_("Total Attendance Days"),
	N_("Shift Details"),
	N_("Shift Location"),
	N_("Shift Schedule Assignment"),
	N_("Shift Dates"),
	N_("Shift Timing"),
	N_("Total Shift Days"),
	# Elsewhere in the app
	N_("View Details"),
	N_("Download Failed"),
	N_("submission"),
)
