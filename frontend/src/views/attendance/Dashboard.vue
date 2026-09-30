<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<PageHeader :title="__('Attendance')" :subtitle="__('Your record and its analysis')" />

			<div class="mx-4 mt-3 flex items-center justify-between rounded-2xl bg-white p-1 shadow-sm">
				<button type="button" class="flex h-10 w-10 items-center justify-center rounded-xl text-brand-roots" :aria-label="__('Previous month')" @click="shiftMonth(-1)">
					<AppIcon name="back" :size="20" />
				</button>
				<span class="text-[15px] font-bold text-brand-ink">{{ monthStart.format("MMMM YYYY") }}</span>
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl text-brand-roots disabled:opacity-30"
					:aria-label="__('Next month')"
					:disabled="isCurrentMonth"
					@click="shiftMonth(1)"
				>
					<AppIcon name="forward" :size="20" />
				</button>
			</div>

			<section class="mx-4 mt-3 grid grid-cols-4 gap-2" :aria-label="__('Month summary')">
				<div v-for="tile in tiles" :key="tile.label" class="rounded-[18px] bg-white px-2.5 py-3 shadow-sm">
					<div class="flex items-center gap-1.5 text-xs text-brand-muted">
						<span class="h-2 w-2 shrink-0 rounded-full" :class="tile.dot" />
						<span class="truncate">{{ tile.label }}</span>
					</div>
					<div class="mt-1 text-[22px] font-bold text-brand-ink">{{ tile.value }}</div>
				</div>
			</section>

			<section class="ms-card mx-4 mt-3 p-4" :aria-label="__('Attendance Calendar')">
				<div class="grid grid-cols-7 gap-1.5 text-center text-xs font-semibold text-brand-muted">
					<span v-for="name in weekdayNames" :key="name" class="truncate">{{ name }}</span>
				</div>
				<div class="mt-2 grid grid-cols-7 gap-1.5 text-center text-sm font-semibold">
					<span v-for="blank in leadingBlanks" :key="`b${blank}`" />
					<button
						v-for="day in days"
						:key="day.date"
						type="button"
						class="flex h-10 items-center justify-center rounded-xl transition"
						:class="[dayClass(day), selectedDate === day.date && 'ring-2 ring-brand-roots ring-offset-1']"
						:aria-label="`${dayjs(day.date).format('D MMMM')}: ${statusLabel(day.status)}`"
						@click="selectedDate = day.date"
					>
						{{ dayjs(day.date).date() }}
					</button>
				</div>

				<div v-if="selectedDay" class="mt-3 rounded-2xl bg-brand-sand px-3.5 py-2.5 text-[13.5px] text-brand-ink">
					<div class="font-bold">{{ dayjs(selectedDay.date).format("dddd D MMMM") }} · {{ statusLabel(selectedDay.status) }}</div>
					<div v-if="selectedDay.first_in" class="text-brand-muted">
						{{ __("In {0}", [clock(selectedDay.first_in)]) }}
						<template v-if="selectedDay.last_out"> · {{ __("Out {0}", [clock(selectedDay.last_out)]) }}</template>
						<template v-if="selectedDay.hours"> · {{ __("{0} h", [formatNumber(selectedDay.hours, 1)]) }}</template>
					</div>
					<div v-else-if="selectedDay.holiday" class="text-brand-muted">{{ __(selectedDay.holiday) }}</div>
				</div>

				<div class="mt-3.5 flex flex-wrap gap-x-3.5 gap-y-1.5 border-t border-brand-roots/[.08] pt-3 text-xs text-brand-muted">
					<span v-for="item in legend" :key="item.label" class="inline-flex items-center gap-1.5">
						<span class="h-2.5 w-2.5 rounded-[3px]" :class="item.swatch" />
						{{ item.label }}
					</span>
				</div>
			</section>

			<section v-if="summary.hours > 0" class="ms-card mx-4 mt-3 p-4" :aria-label="__('Working hours')">
				<div class="flex items-start justify-between gap-3">
					<div>
						<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Working hours") }}</h2>
						<div class="ms-caption">{{ __("One column per working day") }}</div>
					</div>
					<div class="text-end">
						<div class="text-[22px] font-bold text-brand-ink">
							{{ formatNumber(summary.hours, 1) }} <span class="text-[13px] font-semibold text-brand-muted">{{ __("h") }}</span>
						</div>
						<div class="ms-caption">{{ __("Average {0} h/day", [formatNumber(summary.avg_hours, 1)]) }}</div>
					</div>
				</div>
				<ColumnChart class="mt-4" :items="hourColumns" :bar-width="8" :height="90" labels="ends" />
			</section>

			<section class="ms-card mx-4 mt-3 p-4" :aria-label="__('Check-in log')">
				<div class="flex items-center justify-between">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Check-in log") }}</h2>
					<router-link :to="{ name: 'EmployeeCheckinListView' }" class="ms-link">{{ __("View all") }}</router-link>
				</div>
				<ol v-if="recent.length" class="mt-1">
					<li v-for="(day, index) in recent" :key="day.date" class="flex gap-3">
						<div class="flex flex-col items-center pt-1">
							<span
								class="h-3 w-3 rounded-full"
								:class="index === 0 && day.in_progress ? 'bg-brand-emerald ring-4 ring-brand-emerald/[.18]' : 'bg-brand-roots/[.18]'"
							/>
							<span v-if="index < recent.length - 1" class="mt-1 w-0.5 grow bg-brand-roots/[.08]" />
						</div>
						<div class="grow pb-3.5">
							<div class="flex justify-between gap-2">
								<span class="text-[14.5px] font-bold text-brand-ink">{{ dayName(day.date) }}</span>
								<span class="text-[12.5px] font-semibold" :class="day.in_progress ? 'text-brand-emerald' : 'text-brand-ink/80'">
									{{ day.in_progress ? __("In progress") : day.hours ? hoursText(day.hours) : "" }}
								</span>
							</div>
							<div class="mt-0.5 text-[13.5px] text-brand-muted">
								{{ __("In {0}", [clock(day.first_in)]) }}
								<template v-if="day.last_out"> · {{ __("Out {0}", [clock(day.last_out)]) }}</template>
								<template v-else-if="!day.in_progress"> · {{ __("No check-out") }}</template>
							</div>
						</div>
					</li>
				</ol>
				<div v-else class="ms-caption py-4 text-center">{{ __("No check-ins in the last month") }}</div>
			</section>

			<section v-if="upcomingShifts.length" class="ms-card mx-4 mt-3 px-4 pb-1 pt-4" :aria-label="__('Upcoming Shifts')">
				<div class="flex items-center justify-between">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Upcoming Shifts") }}</h2>
					<router-link :to="{ name: 'ShiftAssignmentListView' }" class="ms-link">{{ __("View all") }}</router-link>
				</div>
				<div v-for="shift in upcomingShifts" :key="shift.name" class="ms-list-row">
					<span class="ms-icon-tile" :class="TONES.emerald"><AppIcon name="swap" /></span>
					<span class="min-w-0 grow">
						<span class="block truncate text-[15px] font-semibold text-brand-ink">{{ __(shift.shift_type) }}</span>
						<span class="block truncate text-[12.5px] text-brand-muted">{{ shift.shift_dates }}</span>
					</span>
					<span dir="ltr" class="ms-num text-[13px] font-semibold text-brand-ink/80">{{ shift.shift_timing }}</span>
				</div>
			</section>

			<div class="mx-4 mb-8 mt-3 grid grid-cols-2 gap-2.5">
				<router-link :to="{ name: 'AttendanceRequestFormView' }" class="ms-secondary-button">
					<AppIcon name="calendar-check" :size="18" />
					{{ __("Request Attendance") }}
				</router-link>
				<router-link :to="{ name: 'ShiftRequestFormView' }" class="ms-secondary-button">
					<AppIcon name="swap" :size="18" />
					{{ __("Request a Shift") }}
				</router-link>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"
import { createResource } from "frappe-ui"

import PageHeader from "@/components/ui/PageHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import ColumnChart from "@/components/ui/ColumnChart.vue"

import { attendanceMonth } from "@/data/pwa"
import { getShiftDates, getShiftTiming } from "@/data/attendance"
import { TONES } from "@/utils/requestTypes"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const monthStart = ref(dayjs().startOf("month"))
const isCurrentMonth = computed(() => monthStart.value.isSame(dayjs(), "month"))
const selectedDate = ref(dayjs().format("YYYY-MM-DD"))

function shiftMonth(step) {
	monthStart.value = monthStart.value.add(step, "month")
	selectedDate.value = null
}

watch(monthStart, (value) => attendanceMonth.submit({ month: value.format("YYYY-MM") }), { immediate: true })

async function refresh(event) {
	await Promise.allSettled([attendanceMonth.submit({ month: monthStart.value.format("YYYY-MM") }), shifts.reload()])
	event.target.complete()
}

const data = computed(() => (attendanceMonth.data?.month === monthStart.value.format("YYYY-MM") ? attendanceMonth.data : null))
const days = computed(() => data.value?.days || [])
const summary = computed(() => data.value?.summary || {})
const recent = computed(() => data.value?.recent || [])
const selectedDay = computed(() => days.value.find((day) => day.date === selectedDate.value))

const tiles = computed(() => [
	{ label: __("Present"), value: summary.value.present ?? "–", dot: "bg-state-success" },
	{ label: __("Late"), value: summary.value.late ?? "–", dot: "bg-state-warning" },
	{ label: __("On Leave"), value: summary.value.leave ?? "–", dot: "bg-state-info" },
	{ label: __("Absent"), value: summary.value.absent ?? "–", dot: "bg-state-danger" },
])

// Weekday columns start with the employee's first working day of the week.
const firstWeekday = computed(() => ((data.value?.first_weekday ?? 6) + 1) % 7) // Python Monday=0 → JS Sunday=0
const weekdayNames = computed(() =>
	Array.from({ length: 7 }, (_, i) => dayjs().day((firstWeekday.value + i) % 7).format("ddd"))
)
const leadingBlanks = computed(() => {
	const first = monthStart.value.day()
	return Array.from({ length: (first - firstWeekday.value + 7) % 7 }, (_, i) => i)
})

const STATUS = {
	on_time: { label: __("On time"), cell: "bg-state-success/[.14] text-state-success-text" },
	present: { label: __("Present"), cell: "bg-state-success/[.14] text-state-success-text" },
	late: { label: __("Late"), cell: "bg-state-warning/[.18] text-state-warning-text" },
	leave: { label: __("On Leave"), cell: "bg-state-info/[.14] text-state-info-text" },
	absent: { label: __("Absent"), cell: "bg-state-danger/[.12] text-state-danger-text" },
	holiday: { label: __("Holiday"), cell: "bg-brand-roots/[.08] text-brand-ink/70" },
	weekly_off: { label: __("Weekly off"), cell: "text-brand-ink/40" },
	today: { label: __("Today"), cell: "bg-white text-brand-emerald ring-2 ring-inset ring-brand-emerald" },
	future: { label: "", cell: "text-brand-ink/40" },
}
const statusLabel = (status) => STATUS[status]?.label || ""
const dayClass = (day) => {
	if (day.date === dayjs().format("YYYY-MM-DD") && day.status !== "leave" && day.status !== "holiday")
		return day.status === "today" ? STATUS.today.cell : `${STATUS[day.status]?.cell} ring-2 ring-inset ring-brand-emerald`
	return STATUS[day.status]?.cell
}

const legend = [
	{ label: __("On time"), swatch: "bg-state-success/[.14]" },
	{ label: __("Late"), swatch: "bg-state-warning/[.18]" },
	{ label: __("On Leave"), swatch: "bg-state-info/[.14]" },
	{ label: __("Absent"), swatch: "bg-state-danger/[.12]" },
	{ label: __("Holiday"), swatch: "bg-brand-roots/[.08]" },
]

const clock = (time) => dayjs(`2000-01-01 ${time}`).format("h:mm a")
const hoursText = (hours) => __("{0} h {1} m", [Math.floor(hours), Math.round((hours % 1) * 60)])
const dayName = (date) => {
	const day = dayjs(date)
	if (day.isToday()) return __("Today")
	if (day.isYesterday()) return __("Yesterday")
	return day.format("dddd D MMMM")
}

const hourColumns = computed(() =>
	days.value
		.filter((day) => ["on_time", "late", "present"].includes(day.status))
		.map((day) => ({
			key: day.date,
			label: dayjs(day.date).isToday() ? __("Today") : dayjs(day.date).format("D MMM"),
			value: day.hours,
			display: `${dayjs(day.date).format("D MMM")} · ${__("{0} h", [formatNumber(day.hours, 1)])}`,
			accent: dayjs(day.date).isToday(),
		}))
)

const shifts = createResource({
	url: "hrms.api.get_shifts",
	auto: true,
	cache: "hrms:shifts",
	transform: (data) =>
		data.map((assignment) => ({
			...assignment,
			is_upcoming: !assignment.end_date || dayjs(assignment.end_date).isAfter(dayjs()),
			shift_dates: getShiftDates(assignment),
			shift_timing: getShiftTiming(assignment),
		})),
})
const upcomingShifts = computed(() => (shifts.data || []).filter((shift) => shift.is_upcoming).slice(0, 3))
</script>
