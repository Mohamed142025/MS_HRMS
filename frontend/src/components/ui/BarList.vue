<template>
	<!-- Amounts by category as ranked horizontal bars: one hue, length is the value. -->
	<ul class="flex flex-col gap-3">
		<li v-for="row in rows" :key="row.label">
			<div class="flex items-baseline justify-between gap-3 text-[14px]">
				<span class="truncate text-brand-ink">{{ row.label }}</span>
				<span class="ms-num shrink-0 font-semibold text-brand-ink">{{ row.display }}</span>
			</div>
			<div class="mt-1.5 h-2 rounded-full bg-brand-emerald/[.12]">
				<div
					class="h-2 rounded-full"
					:class="row.tone || 'bg-brand-emerald'"
					:style="{ width: `${Math.max((row.value / max) * 100, 2)}%` }"
				/>
			</div>
		</li>
	</ul>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
	rows: { type: Array, required: true },
})

const max = computed(() => Math.max(...props.rows.map((row) => row.value), 1))
</script>
