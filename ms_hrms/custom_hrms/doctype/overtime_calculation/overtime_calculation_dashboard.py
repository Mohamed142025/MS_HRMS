from frappe import _


def get_data():

    return {
        "fieldname": "ref_docname",

        "non_standard_fieldnames": {
            "Additional Salary": "ref_docname",
        },

        "transactions": [
            {
                "label": _("Payroll"),
                "items": [
                    "Additional Salary",
                ],
            },
        ],
    }