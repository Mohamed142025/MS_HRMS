<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Overtime Request"
				v-model="overtimeRequest"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="true"
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { inject, ref } from "vue"
import FormView from "@/components/FormView.vue"

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

const sessionEmployee = inject("$employee")
const currEmployee = ref(sessionEmployee?.data?.name || "")
const overtimeRequest = ref({
	employee: currEmployee.value,
})

const hiddenEmployeeFields = [
	"employee",
	"employee_name",
	"department",
	"designation",
	"company",
]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Overtime Request" },
	transform(data) {
		const fields = data.filter((field) => !["naming_series"].includes(field.fieldname))

		return fields.map((field) => {
			if (hiddenEmployeeFields.includes(field.fieldname)) {
				field.hidden = true
				field.read_only = true
			}

			// Not asked of the employee: the cost center is theirs (set on the server).
			if (field.fieldname === "project") field.hidden = true
			if (field.fieldname === "cost_center") field.read_only = true

			if (field.fieldname === "employee") {
				field.default = currEmployee.value
			}

			return field
		})
	},
})
formFields.reload()

// The employee's cost center, shown read only; the server sets it anyway.
createResource({
	url: "ms_hrms.custom_hrms.doctype.overtime_request.overtime_request.get_cost_center",
	params: { employee: currEmployee.value },
	auto: !props.id && Boolean(currEmployee.value),
	onSuccess(costCenter) {
		if (costCenter && !overtimeRequest.value.cost_center) overtimeRequest.value.cost_center = costCenter
	},
})

function validateForm() { return true }
</script>
