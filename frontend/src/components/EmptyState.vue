<template>
	<div
		class="flex flex-col items-center rounded-[22px] p-6 text-center text-[13.5px] text-brand-muted"
		:class="props.isTableField ? 'mt-5 border-[1.5px] border-dashed border-brand-roots/[.12]' : ''"
	>
		{{ __(props.message) }}
	</div>
</template>

<script setup>
const props = defineProps({
	message: { type: String },
	isTableField: { type: Boolean, default: false },
})
</script>
