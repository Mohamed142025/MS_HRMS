<template>
	<!-- A request's details and actions: Frappe HR's request sheet, as a bottom sheet. -->
	<ion-modal :is-open="Boolean(request)" :initial-breakpoint="1" :breakpoints="[0, 1]" class="ms-sheet" @didDismiss="$emit('close')">
		<RequestActionSheet v-if="request" :fields="FIELDS[request.doctype]" :model-value="request" />
	</ion-modal>
</template>

<script setup>
import { IonModal } from "@ionic/vue"
import RequestActionSheet from "@/components/RequestActionSheet.vue"
import {
	LEAVE_FIELDS,
	EXPENSE_CLAIM_FIELDS,
	ATTENDANCE_REQUEST_FIELDS,
	SHIFT_REQUEST_FIELDS,
	PERMISSION_REQUEST_FIELDS,
	OVERTIME_REQUEST_FIELDS,
} from "@/data/config/requestSummaryFields"

defineProps({ request: { type: Object, default: null } })
defineEmits(["close"])

const FIELDS = {
	"Leave Application": LEAVE_FIELDS,
	"Expense Claim": EXPENSE_CLAIM_FIELDS,
	"Attendance Request": ATTENDANCE_REQUEST_FIELDS,
	"Shift Request": SHIFT_REQUEST_FIELDS,
	"Permission Request": PERMISSION_REQUEST_FIELDS,
	"Overtime Request": OVERTIME_REQUEST_FIELDS,
}
</script>
