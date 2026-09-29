<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<LeaveIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800">
					{{ __(props.doc.permission_type || "Permission") }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ formatDate(props.doc.permission_date) }}</span>
					<span v-if="props.doc.from_time || props.doc.to_time">
						<span class="whitespace-pre"> &middot; </span>
						<span class="whitespace-nowrap">{{ formatTimeRange(props.doc) }}</span>
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge variant="outline" :theme="colorMap[status]" :label="__(status)" size="md" />
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed } from "vue"
import { Badge, FeatherIcon } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import dayjs from "@/utils/dayjs"

const props = defineProps({
	doc: {
		type: Object,
	},
	isTeamRequest: {
		type: Boolean,
		default: false,
	},
	workflowStateField: {
		type: String,
		required: false,
	},
})

const status = computed(() => {
	if (props.workflowStateField) return props.doc[props.workflowStateField]
	return props.doc.status || (props.doc.docstatus ? "Submitted" : "Draft")
})

const formatDate = (value) => (value ? dayjs(value).format("D MMM") : "")
const formatTimeRange = (request) => {
	if (!request.from_time && !request.to_time) return ""
	const start = request.from_time ? request.from_time.slice(0, 5) : "00:00"
	const end = request.to_time ? request.to_time.slice(0, 5) : "00:00"
	return `${start} - ${end}`
}

const colorMap = {
	Draft: "gray",
	Open: "orange",
	Pending: "blue",
	Approved: "green",
	Rejected: "red",
	Cancelled: "gray",
}
</script>
