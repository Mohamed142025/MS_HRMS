<template>
	<!-- A progress ring (meter): the fill is the value, the track a light step of it. -->
	<div class="relative shrink-0" :style="{ width: `${size}px`, height: `${size}px` }">
		<svg :width="size" :height="size" viewBox="0 0 120 120" aria-hidden="true">
			<circle cx="60" cy="60" :r="radius" fill="none" stroke="currentColor" :stroke-width="stroke" :class="trackClass" />
			<circle
				v-if="length > 0"
				cx="60"
				cy="60"
				:r="radius"
				fill="none"
				stroke="currentColor"
				:stroke-width="stroke"
				stroke-linecap="round"
				:stroke-dasharray="`${length} ${circumference}`"
				transform="rotate(-90 60 60)"
				:class="colorClass"
			/>
		</svg>
		<div class="absolute inset-0 flex flex-col items-center justify-center text-center">
			<slot />
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
	value: { type: Number, default: 0 },
	size: { type: Number, default: 124 },
	stroke: { type: Number, default: 12 },
	colorClass: { type: String, default: "text-brand-emerald" },
	trackClass: { type: String, default: "text-brand-emerald/[.12]" },
})

const radius = computed(() => 60 - props.stroke / 2 - 1)
const circumference = computed(() => 2 * Math.PI * radius.value)
const length = computed(() => (Math.min(Math.max(props.value || 0, 0), 100) / 100) * circumference.value)
</script>
