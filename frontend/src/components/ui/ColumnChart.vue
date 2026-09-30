<template>
	<!-- One series of columns from a common baseline. Tapping a column shows its value;
	     the accented column (today, the latest month) shows its value to begin with. -->
	<div>
		<div class="relative" :style="{ height: `${height + 28}px` }">
			<template v-if="target">
				<div
					class="pointer-events-none absolute inset-x-0 border-t border-brand-roots/[.18]"
					:style="{ bottom: `${barHeight(target.value) + 1}px` }"
				/>
				<span
					class="ms-num pointer-events-none absolute end-0 text-[11px] text-brand-muted"
					:style="{ bottom: `${barHeight(target.value) + 4}px` }"
				>
					{{ target.label }}
				</span>
			</template>
			<div class="absolute inset-0 flex items-end justify-between gap-1">
				<button
					v-for="(item, index) in items"
					:key="item.key || index"
					type="button"
					class="relative flex h-full flex-1 flex-col items-center justify-end"
					:aria-label="`${item.label}: ${item.display}`"
					@click="selected = index"
				>
					<span
						v-if="selected === index && item.display"
						class="ms-num absolute z-10 whitespace-nowrap rounded-lg bg-brand-roots px-2 py-0.5 text-[11.5px] font-bold text-white"
						:style="{ bottom: `${barHeight(item.value) + 6}px` }"
					>
						{{ item.display }}
					</span>
					<span
						class="block rounded-t-[4px] transition-all"
						:class="item.accent ? 'bg-brand-roots' : 'bg-brand-emerald'"
						:style="{ width: `${barWidth}px`, height: `${barHeight(item.value)}px`, opacity: item.value ? 1 : 0 }"
					/>
				</button>
			</div>
		</div>
		<div class="mt-2 flex justify-between gap-1 border-t border-brand-roots/[.12] pt-2">
			<span
				v-for="(item, index) in items"
				:key="`l${item.key || index}`"
				class="flex-1 text-[11.5px]"
				:class="[item.accent ? 'font-bold text-brand-roots' : 'text-brand-muted', labelClass(index)]"
			>
				{{ showLabel(index) ? item.label : "" }}
			</span>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"

const props = defineProps({
	// [{ key, label, value, display, accent }]
	items: { type: Array, required: true },
	height: { type: Number, default: 110 },
	barWidth: { type: Number, default: 22 },
	max: { type: Number, default: 0 },
	// { value, label }: a reference line, such as the hours of a shift.
	target: { type: Object, default: null },
	// "all", or "ends": only the first, the last and the accented column are labelled.
	labels: { type: String, default: "all" },
})

// Sparse labels may be wider than their column: they overflow into the empty neighbours.
const labelClass = (index) => {
	if (props.labels === "all") return "truncate text-center"
	if (index === 0) return "whitespace-nowrap text-start"
	if (index === props.items.length - 1) return "whitespace-nowrap text-end"
	return "whitespace-nowrap text-center"
}

const showLabel = (index) =>
	props.labels === "all" || index === 0 || index === props.items.length - 1 || props.items[index].accent

const top = computed(() =>
	Math.max(props.max, props.target?.value || 0, ...props.items.map((item) => item.value || 0), 1)
)
const barHeight = (value) => Math.round(((value || 0) / top.value) * props.height)

const selected = ref(props.items.findIndex((item) => item.accent))
</script>
