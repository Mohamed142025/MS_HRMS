<template>
	<!-- A request in a list: its type's icon, what and when, and its status. -->
	<button type="button" class="ms-list-row" @click="$emit('open', doc)">
		<span class="ms-icon-tile" :class="TONES[type.tone]"><AppIcon :name="type.icon" /></span>
		<span class="min-w-0 grow">
			<span class="block truncate text-[15px] font-semibold text-brand-ink">{{ requestTitle(doc) }}</span>
			<span class="block truncate text-[13px] text-brand-muted">
				<template v-if="showEmployee">{{ doc.employee_name }} · </template>{{ requestDetails(doc) }}
			</span>
		</span>
		<StatusChip :status="requestStatus(doc)" />
	</button>
</template>

<script setup>
import { computed } from "vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import StatusChip from "@/components/ui/StatusChip.vue"
import { REQUEST_TYPES, TONES, requestDetails, requestStatus, requestTitle } from "@/utils/requestTypes"

const props = defineProps({
	doc: { type: Object, required: true },
	showEmployee: { type: Boolean, default: false },
})
defineEmits(["open"])

const type = computed(() => REQUEST_TYPES[props.doc.doctype] || { icon: "file", tone: "neutral" })
</script>
