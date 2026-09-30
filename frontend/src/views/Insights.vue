<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('Insights')" :subtitle="periodLabel" fallback="/home" />

			<Segmented v-model="period" :options="periods" class="mx-4 mt-4" />

			<div v-if="!data" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<template v-else>
				<section class="ms-dark-card mx-4 mt-4 p-[18px]" :aria-label="__('Discipline index')">
					<div class="flex items-center gap-4">
						<Ring :value="data.index || 0" :size="132" :stroke="10" color-class="text-brand-mint" track-class="text-brand-sand/[.12]">
							<span class="text-[36px] font-bold leading-none">{{ data.index ?? "–" }}</span>
							<span class="mt-1 text-xs text-brand-sand/70">{{ __("of 100") }}</span>
						</Ring>
						<div class="min-w-0">
							<div class="text-[13px] text-brand-sand/70">{{ __("Discipline index") }}</div>
							<div class="mt-0.5 text-[22px] font-bold text-brand-mint">{{ indexLabel }}</div>
							<div v-if="indexDelta" class="mt-1.5 text-[13.5px] leading-6 text-brand-sand/85">{{ indexDelta }}</div>
						</div>
					</div>
					<div class="mt-4 grid grid-cols-3 gap-2">
						<div v-for="tile in indexTiles" :key="tile.label" class="rounded-2xl bg-brand-sand/[.06] px-3 py-2.5">
							<div class="text-lg font-bold">{{ tile.value }}</div>
							<div class="text-xs text-brand-sand/70">{{ tile.label }}</div>
						</div>
					</div>
					<p class="mt-3 text-xs leading-5 text-brand-sand/60">{{ __("Punctuality counts for half, attendance for 40% and leaving on time for 10%.") }}</p>
				</section>

				<section class="mx-4 mt-3 grid grid-cols-2 gap-3" :aria-label="__('This period')">
					<div v-for="kpi in kpis" :key="kpi.label" class="ms-card p-3.5">
						<div class="text-[13px] font-semibold text-brand-muted">{{ kpi.label }}</div>
						<div class="mt-1.5 text-[24px] font-bold text-brand-ink">
							{{ kpi.value }}
							<span class="text-[13px] font-semibold text-brand-muted">{{ kpi.unit }}</span>
						</div>
						<div class="mt-0.5 text-xs font-semibold" :class="kpi.tone || 'text-brand-muted'">{{ kpi.note }}</div>
					</div>
				</section>

				<section class="ms-card mx-4 mt-3 p-4" :aria-label="__('Punctuality')">
					<div class="flex items-start justify-between gap-2">
						<div>
							<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Punctuality") }}</h2>
							<div class="ms-caption">{{ __("Last 6 months") }}</div>
						</div>
					</div>
					<LineChart v-if="trendPoints.some((p) => p.value !== null)" class="mt-3" :points="trendPoints" />
					<div v-else class="ms-caption py-6 text-center">{{ __("Needs a shift to judge arrival times") }}</div>
				</section>

				<section v-if="data.shift && data.arrivals.length" class="ms-card mx-4 mt-3 p-4" :aria-label="__('Your arrival times')">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Your arrival times") }}</h2>
					<div class="ms-caption">{{ __("Each dot is a working day. The line is the start of your shift.") }}</div>
					<div class="relative mt-4" :style="{ height: `${arrivalRows * 13 + 16}px` }">
						<span class="absolute bottom-2 left-2 right-2 h-0.5 rounded-full bg-brand-roots/[.08]" />
						<span class="absolute bottom-0 top-0 w-px bg-brand-roots/[.28]" :style="{ left: `${startX}%` }" />
						<span
							v-for="(dot, index) in arrivalDots"
							:key="index"
							class="absolute h-2.5 w-2.5 -translate-x-1/2 rounded-full ring-2 ring-white"
							:class="dot.late ? 'bg-state-warning' : 'bg-brand-emerald'"
							:style="{ left: `${dot.x}%`, bottom: `${12 + dot.row * 13}px` }"
							:title="`${dot.date}: ${dot.label}`"
						/>
					</div>
					<div class="relative mt-2 h-4 text-[11.5px] text-brand-muted" dir="ltr">
						<span v-if="startX > 24" class="absolute left-0">{{ axisLabels.left }}</span>
						<span class="absolute -translate-x-1/2 whitespace-nowrap font-bold text-brand-roots" :style="{ left: `${Math.min(Math.max(startX, 9), 91)}%` }">
							{{ clock(data.shift.start) }}
						</span>
						<span v-if="startX < 76" class="absolute right-0">{{ axisLabels.right }}</span>
					</div>
					<div class="mt-3 flex gap-4 text-xs text-brand-muted">
						<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-brand-emerald" />{{ __("On time") }}</span>
						<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-state-warning" />{{ __("Late") }}</span>
					</div>

					<div class="mt-4 grid gap-1.5 text-center" :style="{ gridTemplateColumns: `repeat(${data.late_by_weekday.length}, minmax(0, 1fr))` }">
						<div
							v-for="day in data.late_by_weekday"
							:key="day.weekday"
							class="rounded-xl py-2"
							:class="day.count ? 'bg-state-warning/[.12] text-state-warning-text' : 'bg-brand-sand text-brand-ink/70'"
						>
							<div class="text-[15px] font-bold">{{ day.count }}</div>
							<div class="text-[11px]">{{ __(day.weekday) }}</div>
						</div>
					</div>
					<div class="ms-caption mt-2">{{ __("Late arrivals by weekday") }}</div>
				</section>

				<section v-if="data.notes.length" class="mx-4 mb-8 mt-6" :aria-label="__('Notes for you')">
					<h2 class="ms-section-title mb-3">{{ __("Notes for you") }}</h2>
					<div class="flex flex-col gap-2.5">
						<div v-for="(note, index) in data.notes" :key="index" class="ms-card flex items-start gap-3 p-3.5">
							<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" :class="TONES[noteTone(note)]">
								<AppIcon :name="noteIcon(note)" :size="20" />
							</span>
							<div class="min-w-0">
								<p class="text-[14.5px] leading-7 text-brand-ink">{{ note.text }}</p>
								<router-link v-if="note.action && note.action.route !== 'Insights'" :to="{ name: note.action.route }" class="ms-link">
									{{ note.action.label }}
								</router-link>
							</div>
						</div>
					</div>
				</section>
				<div v-else class="h-8" />
			</template>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { IonPage, IonContent } from "@ionic/vue"

import SubHeader from "@/components/ui/SubHeader.vue"
import Segmented from "@/components/ui/Segmented.vue"
import Ring from "@/components/ui/Ring.vue"
import LineChart from "@/components/ui/LineChart.vue"
import AppIcon from "@/components/ui/AppIcon.vue"

import { insights } from "@/data/pwa"
import { TONES } from "@/utils/requestTypes"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const period = ref("month")
const periods = [
	{ value: "month", label: __("This month") },
	{ value: "quarter", label: __("3 months") },
	{ value: "year", label: __("12 months") },
]

watch(period, (value) => insights.submit({ period: value }), { immediate: true })

const data = computed(() => (insights.data?.period === period.value ? insights.data : null))
const periodLabel = computed(() => {
	if (!data.value) return ""
	return `${dayjs(data.value.from_date).format("D MMM YYYY")} – ${dayjs().format("D MMM YYYY")}`
})

const clock = (time) => dayjs(`2000-01-01 ${time}`).format("h:mm a")

const indexLabel = computed(() => {
	const index = data.value?.index
	if (index === null || index === undefined) return __("Not enough data")
	if (index >= 90) return __("Excellent")
	if (index >= 75) return __("Good")
	if (index >= 60) return __("Fair")
	return __("Needs improvement")
})

const indexDelta = computed(() => {
	const { index, previous_index: before } = data.value || {}
	if (index === null || index === undefined || before === null || before === undefined) return ""
	const change = index - before
	if (change > 0) return __("{0} points higher than the previous period", [change])
	if (change < 0) return __("{0} points lower than the previous period", [-change])
	return __("Same as the previous period")
})

const percent = (value) => (value === null || value === undefined ? "–" : `${value}%`)

const indexTiles = computed(() => {
	const summary = data.value.summary
	return [
		{ label: __("On time"), value: percent(summary.punctuality) },
		{ label: __("Attendance rate"), value: percent(summary.attendance_rate) },
		{ label: __("Early exits"), value: summary.early_exits },
	]
})

function delta(current, before, unit, higherIsBetter = true) {
	if (!before && !current) return { note: "", tone: "" }
	const change = Math.round((current - before) * 10) / 10
	if (!change) return { note: __("Same as the previous period"), tone: "" }
	const good = change > 0 === higherIsBetter
	return {
		note: `${change > 0 ? "▲" : "▼"} ${formatNumber(Math.abs(change), 1)} ${unit} ${__("vs previous period")}`,
		tone: good ? "text-state-success-text" : "text-state-warning-text",
	}
}

const kpis = computed(() => {
	const { summary, previous } = data.value
	return [
		{
			label: __("Average working hours"),
			value: formatNumber(summary.avg_hours, 1),
			unit: __("h/day"),
			...delta(summary.avg_hours, previous.avg_hours, __("h")),
		},
		{
			label: __("Overtime"),
			value: formatNumber(data.value.overtime_hours, 1),
			unit: __("hours"),
			...delta(data.value.overtime_hours, data.value.previous_overtime_hours, __("h")),
		},
		{
			label: __("Days present"),
			value: summary.present,
			unit: summary.expected ? __("of {0}", [summary.expected]) : "",
			note: summary.leave ? __("and {0} days on leave", [summary.leave]) : "",
		},
		{
			label: __("Permission hours"),
			value: formatNumber(data.value.permission_hours, 1),
			unit: __("hours"),
			note: summary.late ? __("{0} late arrivals", [summary.late]) : __("No late arrivals"),
		},
	]
})

const trendPoints = computed(() =>
	(data.value?.trend || []).map((month) => ({
		label: dayjs(`${month.month}-01`).format("MMM"),
		value: month.punctuality,
		display: month.punctuality === null ? "" : `${month.punctuality}%`,
	}))
)

// Arrival dots: minutes after the shift start, on an axis from before to after it.
const range = computed(() => {
	const minutes = (data.value?.arrivals || []).map((a) => a.minutes)
	const low = Math.max(Math.min(-30, ...minutes), -120)
	const high = Math.min(Math.max(45, ...minutes), 240)
	return { low, high }
})
const position = (minutes) => {
	const { low, high } = range.value
	const share = (Math.min(Math.max(minutes, low), high) - low) / (high - low)
	return 4 + share * 92
}
const startX = computed(() => position(0))
const arrivalDots = computed(() => {
	const rows = {}
	return (data.value?.arrivals || []).map((arrival) => {
		const bucket = Math.round(arrival.minutes / 4)
		rows[bucket] = (rows[bucket] || 0) + 1
		return {
			...arrival,
			x: position(arrival.minutes),
			row: rows[bucket] - 1,
			label: dayjs(`2000-01-01 ${data.value.shift.start}`).add(arrival.minutes, "minute").format("h:mm a"),
		}
	})
})
const arrivalRows = computed(() => Math.max(...arrivalDots.value.map((dot) => dot.row + 1), 1))
const axisLabels = computed(() => {
	const start = dayjs(`2000-01-01 ${data.value.shift.start}`)
	return {
		left: start.add(range.value.low, "minute").format("h:mm a"),
		right: start.add(range.value.high, "minute").format("h:mm a"),
	}
})

const noteIcon = (note) => ({ leave: "bulb", attendance: "clock", warning: "alert", positive: "trend-up" })[note.kind] || "clock-plus"
const noteTone = (note) => ({ leave: "emerald", attendance: "warning", warning: "danger", positive: "success" })[note.kind] || "info"
</script>
