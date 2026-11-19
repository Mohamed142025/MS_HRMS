<template>
	<!-- How a request was decided: who approved, rejected or cancelled it, when, and the
	     approver's remarks or reason for rejecting (ms_hrms.request_history). -->
	<div v-if="decision.data">
		<div class="rounded-2xl bg-brand-sand/60 p-3.5 text-[14px] leading-6">
			<div class="flex items-center justify-between gap-2">
				<span class="font-bold text-brand-ink">{{ __("Decision") }}</span>
				<StatusChip
					v-if="decision.data.status || decision.data.cancelled_by"
					:status="decision.data.cancelled_by ? 'Cancelled' : decision.data.status"
				/>
			</div>
			<div v-for="row in rows" :key="row.label" class="mt-1.5 flex items-start justify-between gap-3">
				<span class="shrink-0 text-brand-muted">{{ row.label }}</span>
				<span class="text-end text-brand-ink">{{ row.value }}</span>
			</div>
			<div v-if="decision.data.remarks" class="mt-2 border-t border-brand-roots/[.08] pt-2">
				<span class="block text-brand-muted">
					{{ decision.data.status === "Rejected" ? __("Reason for rejection") : __("Approver's remarks") }}
				</span>
				<span class="block whitespace-pre-line text-brand-ink">{{ decision.data.remarks }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from "vue"
import { createResource } from "frappe-ui"

import StatusChip from "@/components/ui/StatusChip.vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({
	doctype: { type: String, required: true },
	name: { type: String, required: true },
	// Reloads when this changes (the request's modified time).
	version: { type: String, default: "" },
})

const decision = createResource({
	url: "ms_hrms.request_history.get_request_decision",
	params: { doctype: props.doctype, name: props.name },
	auto: true,
})
watch(
	() => props.version,
	(value, old) => value && old && value !== old && decision.reload()
)

const when = (value) => (value ? dayjs(value).format("D MMM YYYY · h:mm a") : "")
const rows = computed(() => {
	const data = decision.data || {}
	const decided = data.status === "Rejected" ? __("Rejected by") : __("Approved by")
	return [
		{ label: decided, value: data.status && data.by },
		{ label: __("Decided on"), value: data.status && when(data.on) },
		{ label: __("Cancelled by"), value: data.cancelled_by },
		{ label: __("Cancelled on"), value: when(data.cancelled_on) },
	].filter((row) => row.value)
})

defineExpose({ reload: () => decision.reload(), status: computed(() => decision.data?.status) })
</script>
