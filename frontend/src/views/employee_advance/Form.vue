<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Employee Advance"
				v-model="employeeAdvance"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="true"
				:showFormButton="!canApprove.data"
				@validateForm="validateForm"
			>
				<!-- The employee's manager or approver approves it here, whatever their roles. -->
				<template #formButton>
					<button type="button" class="ms-primary-button w-full" :disabled="approving" @click="approve">
						{{ __("Approve") }}
					</button>
				</template>
				<template #bottom="{ formModel }">
					<AdvanceRepaymentSchedule v-if="props.id && formModel.docstatus === 1" :advance="formModel" />
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource, toast } from "frappe-ui"
import { useRouter } from "vue-router"
import { computed, ref, inject, watch } from "vue"

import AdvanceRepaymentSchedule from "@/components/AdvanceRepaymentSchedule.vue"
import FormView from "@/components/FormView.vue"
import { useCurrencyConversion } from "@/composables/useCurrencyConversion"
import { getCompanyCurrency } from "@/data/currencies"
import { teamAdvances } from "@/data/advances"
import { submit } from "@/composables/approval"

const employee = inject("$employee")
const __ = inject("$translate")
const router = useRouter()

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// object to store form data
const employeeAdvance = ref({
	employee: employee.data.name,
	employee_name: employee.data.employee_name,
	company: employee.data.company,
	department: employee.data.department,
})

// A new advance is in the company's currency unless the employee picks another.
const companyCurrency = computed(() => getCompanyCurrency(employeeAdvance.value.company))
watch(
	companyCurrency,
	(currency) => {
		if (!props.id && currency && !employeeAdvance.value.currency) employeeAdvance.value.currency = currency
	},
	{ immediate: true }
)

// Approving, for the employee's manager or approver (ms_hrms.request_approvers).
const canApprove = createResource({
	url: "ms_hrms.request_approvers.get_can_approve",
	params: { doctype: "Employee Advance", name: props.id },
	auto: Boolean(props.id),
})
const approving = ref(false)

async function approve() {
	approving.value = true
	try {
		await submit({ doctype: "Employee Advance", name: props.id })
		teamAdvances.reload()
		toast({
			title: __("Success"),
			text: __("{0} successfully!", [__("Approved")]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.back()
	} catch (error) {
		toast({
			title: __("Error"),
			text: error.messages?.[0] || __("{0} failed!", [__("Approval")]),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		approving.value = false
	}
}

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Employee Advance" },
	transform(data) {
		const fields = getFilteredFields(data)
		return applyFilters(fields)
	},
})
formFields.reload()

useCurrencyConversion(
	formFields,
	employeeAdvance,
	["paid_amount"]
)

// helper functions
function getFilteredFields(fields) {
	// reduce noise from the form view by excluding unnecessary fields
	// eg: employee and other details can be fetched from the session user
	// The repayment plan shows as its own card (AdvanceRepaymentSchedule).
	const excludeFields = ["naming_series", "base_paid_amount"]
	const extraFields = [
		"employee",
		"employee_name",
		"department",
		"company",
		"more_info_section",
		"pending_amount",
		// Set by accounts and HR once approved, not by the employee asking.
		"advance_account",
		"mode_of_payment",
		"repay_unclaimed_amount_from_salary",
		"return_amount",
		"claimed_amount",
		"paid_amount",
	]

	if (!props.id) excludeFields.push(...extraFields)

	const kept = fields.filter(
		(field) =>
			!excludeFields.includes(field.fieldname) &&
			!/^custom_(repayment|repaid|missed_installments)/.test(field.fieldname)
	)
	return withoutEmptySections(kept)
}

// A section whose fields were all left out goes too, heading and all.
function withoutEmptySections(fields) {
	const isBreak = (field) => ["Section Break", "Tab Break"].includes(field.fieldtype)
	return fields.filter((field, index) => {
		if (!isBreak(field)) return true
		for (const next of fields.slice(index + 1)) {
			if (isBreak(next)) return false
			if (next.fieldtype !== "Column Break" && !next.hidden) return true
		}
		return false
	})
}

function applyFilters(fields) {
	return fields.map((field) => {
		if (field.fieldname === "advance_account") {
			if (!employeeAdvance.value.currency) return field

			field.linkFilters = {
				root_type: "Asset",
				is_group: 0,
				account_type: "Receivable",
				account_currency: employeeAdvance.value.currency,
				company: employeeAdvance.value.company,
			}
		}

		return field
	})
}

watch(
	() => employeeAdvance.value.currency,
	() => {
		applyFilters(formFields.data)
	}
)

function validateForm() {}
</script>