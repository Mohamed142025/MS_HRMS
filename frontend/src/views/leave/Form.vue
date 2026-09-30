<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Leave Application"
				v-model="leaveApplication"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="true"
				@validateForm="validateForm"
			>
				<!-- New applications pick the leave type from cards showing each balance. -->
				<template #top>
					<section v-if="!props.id && typeCards.length" class="mb-3" :aria-label="__('Leave Type')">
						<h3 class="mx-4 mb-2.5 text-[14px] font-bold text-brand-ink/80">{{ __("Leave Type") }}</h3>
						<div class="hide-scrollbar flex gap-2.5 overflow-x-auto px-4 pb-1" role="radiogroup" :aria-label="__('Leave Type')">
							<button
								v-for="card in typeCards"
								:key="card.type"
								type="button"
								role="radio"
								:aria-checked="leaveApplication.leave_type === card.type"
								class="relative w-[140px] shrink-0 rounded-[20px] bg-white p-3.5 text-start transition"
								:class="
									leaveApplication.leave_type === card.type
										? 'border-2 border-brand-emerald shadow-[0_8px_20px_rgba(var(--ms-emerald-rgb,25,123,87),0.14)]'
										: 'border-[1.5px] border-brand-roots/[.12]'
								"
								@click="leaveApplication.leave_type = card.type"
							>
								<span
									v-if="leaveApplication.leave_type === card.type"
									class="absolute end-3 top-3 flex h-[22px] w-[22px] items-center justify-center rounded-full bg-brand-emerald text-white"
								>
									<AppIcon name="check" :size="13" :stroke-width="3" />
								</span>
								<span class="block pe-6 text-[13.5px] font-semibold leading-5 text-brand-ink">{{ __(card.type, null, "Leave Type") }}</span>
								<span class="mt-2 block text-[24px] font-bold text-brand-ink">{{ card.balance }}</span>
								<span class="block text-xs text-brand-muted">{{ card.caption }}</span>
							</button>
						</div>
					</section>
				</template>

				<template #bottom>
					<section
						v-if="leaveApplication.total_leave_days"
						class="mx-4 mt-3 flex items-center justify-between gap-3 rounded-[22px] bg-brand-emerald/[.12] px-4 py-3.5"
						:aria-label="__('Total Leave Days')"
					>
						<span class="text-[14px] font-semibold text-brand-roots">
							{{ __("{0} days", [formatNumber(leaveApplication.total_leave_days, 1)]) }}
						</span>
						<span v-if="balanceAfter !== null" class="text-[14px] font-bold text-brand-roots">
							{{ __("Balance after this request: {0}", [formatNumber(balanceAfter, 2)]) }}
						</span>
					</section>
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { computed, ref, watch, inject, nextTick } from "vue"

import FormView from "@/components/FormView.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { leaveBalance } from "@/data/leaves"
import { formatNumber } from "@/utils/formatters"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const today = dayjs().format("YYYY-MM-DD")

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

const sessionEmployee = inject("$employee")
const currEmployee = ref(sessionEmployee.data.name)

// reactive object to store form data
const leaveApplication = ref({})

// For existing docs, watchers fire during initial data population from the DB.
// This flag prevents setLeaveBalance() from overwriting the stored
// "leave balance before application" value during that initial load.
const isFormInitialized = ref(!props.id)
if (props.id) {
	watch(
		() => leaveApplication.value.name,
		(name) => {
			if (name && !isFormInitialized.value) {
				nextTick(() => {
					isFormInitialized.value = true
				})
			}
		}
	)
}

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Leave Application" },
	transform(data) {
		let fields = getFilteredFields(data)

		return fields.map((field) => {
			if (field.fieldname === "half_day_date") field.hidden = true

			if (field.fieldname === "posting_date") field.default = today

			// New applications choose the type from the cards above the form.
			if (field.fieldname === "leave_type" && !props.id) field.hidden = true

			return field
		})
	},
	onSuccess(_data) {
		leaveApprovalDetails.reload()
		leaveTypes.reload()
	},
})
formFields.reload()

const leaveApprovalDetails = createResource({
	url: "hrms.api.get_leave_approval_details",
	params: { employee: currEmployee.value },
	onSuccess(data) {
		setLeaveApprovers(data)
	},
})

const leaveTypes = createResource({
	url: "hrms.api.get_leave_types",
	params: {
		employee: currEmployee.value,
		date: today,
	},
	onSuccess(data) {
		setLeaveTypes(data)
	},
})

// form scripts
watch(
	() => leaveApplication.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== currEmployee.value) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
		currEmployee.value = employee_id
		leaveTypes.fetch({ employee: currEmployee.value, date: today })
		leaveApprovalDetails.fetch({ employee: currEmployee.value })		
	}
)
watch(
	() => leaveApplication.value.leave_type,
	(leave_type) => setLeaveBalance(leave_type)
)

watch(
	() => leaveApplication.value.half_day,
	(half_day) => setHalfDayDate(half_day)
)

watch(
	() => leaveApplication.value.half_day && leaveApplication.value.half_day_date,
	() => setTotalLeaveDays()
)

watch(
	() => leaveApplication.value.from_date,
	(from_date) => {
		if (!leaveApplication.value.to_date) {
			leaveApplication.value.to_date = from_date
		}

		// fetch leave types for the selected date
		leaveTypes.fetch({
			employee: currEmployee.value,
			date: from_date,
		})
	}
)

watch(
	() => [leaveApplication.value.from_date, leaveApplication.value.to_date],
	([from_date, to_date]) => {
		validateDates(from_date, to_date)
		setHalfDayDateRange()
		setTotalLeaveDays()
	}
)

watch(
	() => leaveApplication.value.leave_approver,
  	(newApprover) => {
			const approverField = formFields.data.find(f => f.fieldname === "leave_approver")
			const selected = approverField?.documentList?.find(opt => opt.value === newApprover)
			leaveApplication.value.leave_approver_name = selected?.label?.split(" : ")[1] || ""
  }
)

// helper functions
function getFilteredFields(fields) {
	// reduce noise from the form view by excluding unnecessary fields
	// ex: employee and other details can be fetched from the session user
	const excludeFields = [
		"naming_series",
		"sb_other_details",
		"salary_slip",
		"letter_head",
	]

	const employeeFields = [
		"employee",
		"employee_name",
		"department",
		"company",
		"follow_via_email",
		"status",
		"posting_date",
	]

	if (!props.id) excludeFields.push(...employeeFields)

	return fields.filter((field) => !excludeFields.includes(field.fieldname))
}

function setFormReadOnly() {
	if (leaveApplication.value.leave_approver === sessionEmployee.data.user_id) return
	formFields.data.map((field) => (field.read_only = true))
}

function validateDates(from_date, to_date) {
	if (!(from_date && to_date)) return

	const error_message =
		from_date > to_date ? __("To Date cannot be before From Date") : ""

	const from_date_field = formFields.data.find(
		(field) => field.fieldname === "from_date"
	)
	from_date_field.error_message = error_message
}

function setTotalLeaveDays() {
	if (!areValuesSet()) return

	const leaveDays = createResource({
		url: "hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days",
		params: {
			employee: currEmployee.value,
			leave_type: leaveApplication.value.leave_type,
			from_date: leaveApplication.value.from_date,
			to_date: leaveApplication.value.to_date,
			half_day: leaveApplication.value.half_day,
			half_day_date: leaveApplication.value.half_day_date,
		},
		onSuccess(data) {
			leaveApplication.value.total_leave_days = data
		},
	})
	leaveDays.reload()
	setLeaveBalance()
}

function setLeaveBalance() {
	if (!areValuesSet()) return
	if (!isFormInitialized.value) return

	const leaveBalance = createResource({
		url: "hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
		params: {
			employee: currEmployee.value,
			date: leaveApplication.value.from_date,
			to_date: leaveApplication.value.to_date,
			leave_type: leaveApplication.value.leave_type,
			consider_all_leaves_in_the_allocation_period: 1,
		},
		onSuccess(data) {
			leaveApplication.value.leave_balance = data
		},
	})
	leaveBalance.reload()
}

function setHalfDayDate(half_day) {
	const half_day_date = formFields.data.find(
		(field) => field.fieldname === "half_day_date"
	)
	half_day_date.hidden = !half_day
	half_day_date.reqd = half_day

	if (!half_day) return

	if (leaveApplication.value.from_date === leaveApplication.value.to_date) {
		leaveApplication.value.half_day_date = leaveApplication.value.from_date
	} else {
		setHalfDayDateRange()
	}
}

function setHalfDayDateRange() {
	const half_day_date = formFields.data.find(
		(field) => field.fieldname === "half_day_date"
	)
	half_day_date.minDate = leaveApplication.value.from_date
	half_day_date.maxDate = leaveApplication.value.to_date
}

function setLeaveApprovers(data) {
	const leave_approver = formFields.data?.find(
		(field) => field.fieldname === "leave_approver"
	)
	leave_approver.reqd = data?.is_mandatory
	leave_approver.documentList = data?.department_approvers.map((approver) => ({
		label: approver.full_name
			? `${approver.name} : ${approver.full_name}`
			: approver.name,
		value: approver.name,
	}))
	if (!leaveApplication.value.leave_approver){
		leaveApplication.value.leave_approver = data?.leave_approver
		leaveApplication.value.leave_approver_name = data?.leave_approver_name
	}
	
}

function setLeaveTypes(data) {
	const leave_type = formFields.data.find(
		(field) => field.fieldname === "leave_type"
	)
	leave_type.documentList = data?.map((leave_type) => ({
		label: leave_type,
		value: leave_type,
	}))

	// A new application starts on the type with the largest balance.
	if (!props.id && !leaveApplication.value.leave_type && data?.length) {
		const withBalance = data.filter((type) => leaveBalance.data?.[type]?.balance_leaves > 0)
		leaveApplication.value.leave_type = (withBalance.length ? withBalance : data).reduce((best, type) =>
			(leaveBalance.data?.[type]?.balance_leaves || 0) > (leaveBalance.data?.[best]?.balance_leaves || 0) ? type : best
		)
	}
}

function areValuesSet() {
	return (
		leaveApplication.value.from_date &&
		leaveApplication.value.to_date &&
		leaveApplication.value.leave_type
	)
}

function validateForm() {
	setHalfDayDate(leaveApplication.value.half_day)
	leaveApplication.value.employee = currEmployee.value
}

// The types the employee may take on the chosen date, with their balances.
const typeCards = computed(() =>
	(leaveTypes.data || []).map((type) => {
		const allocation = leaveBalance.data?.[type]
		return allocation
			? { type, balance: formatNumber(allocation.balance_leaves), caption: __("days available") }
			: { type, balance: "–", caption: __("No balance needed") }
	})
)

const balanceAfter = computed(() => {
	const { leave_balance: balance, total_leave_days: days } = leaveApplication.value
	if (balance === undefined || balance === null || balance === "" || !days) return null
	return Number(balance) - Number(days)
})
</script>
