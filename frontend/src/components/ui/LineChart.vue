<template>
	<!-- One series over time: a 2px line with ringed markers, gaps where there is no
	     value, time running with the reading direction. Tap a point for its value. -->
	<div>
		<div class="relative" :style="{ height: `${height}px` }">
			<svg class="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
				<line
					v-for="line in gridLines"
					:key="line"
					x1="0"
					x2="100"
					:y1="line"
					:y2="line"
					stroke="currentColor"
					class="text-brand-roots/[.08]"
					vector-effect="non-scaling-stroke"
					stroke-width="1"
				/>
				<polyline
					v-for="(segment, index) in segments"
					:key="index"
					:points="segment"
					fill="none"
					stroke="currentColor"
					class="text-brand-emerald"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					vector-effect="non-scaling-stroke"
				/>
			</svg>
			<button
				v-for="point in plotted"
				:key="point.index"
				type="button"
				class="absolute flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center"
				:style="{ left: `${point.x}%`, top: `${point.y}%` }"
				:aria-label="`${point.label}: ${point.display}`"
				@click="selected = point.index"
			>
				<span
					class="block rounded-full ring-2 ring-white"
					:class="point.index === selected ? 'h-3.5 w-3.5 bg-brand-roots' : 'h-2.5 w-2.5 bg-brand-emerald'"
				/>
				<span
					v-if="point.index === selected"
					class="ms-num absolute bottom-full mb-0.5 whitespace-nowrap rounded-lg bg-brand-roots px-2 py-0.5 text-[11.5px] font-bold text-white"
				>
					{{ point.display }}
				</span>
			</button>
		</div>
		<div class="mt-2 grid text-center text-[11.5px] text-brand-muted" :style="{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }">
			<span
				v-for="(point, index) in points"
				:key="index"
				class="truncate"
				:class="index === selected && 'font-bold text-brand-roots'"
			>
				{{ point.label }}
			</span>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"

const props = defineProps({
	// [{ label, value (null for none), display }], oldest first
	points: { type: Array, required: true },
	min: { type: Number, default: 0 },
	max: { type: Number, default: 100 },
	height: { type: Number, default: 120 },
})

const rtl = document.documentElement.dir === "rtl"
const gridLines = [8, 36, 64, 92]

const plotted = computed(() =>
	props.points
		.map((point, index) => {
			if (point.value === null || point.value === undefined) return null
			const across = ((index + 0.5) / props.points.length) * 100
			const share = (point.value - props.min) / (props.max - props.min || 1)
			return { ...point, index, x: rtl ? 100 - across : across, y: 92 - Math.min(Math.max(share, 0), 1) * 84 }
		})
		.filter(Boolean)
)

const segments = computed(() => {
	const runs = []
	let run = []
	let last = -2
	for (const point of plotted.value) {
		if (point.index !== last + 1 && run.length) {
			runs.push(run)
			run = []
		}
		run.push(`${point.x},${point.y}`)
		last = point.index
	}
	if (run.length) runs.push(run)
	return runs.filter((r) => r.length > 1).map((r) => r.join(" "))
})

const selected = ref(plotted.value.length ? plotted.value[plotted.value.length - 1].index : -1)
</script>
