<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<!-- ms-app-header is also a hook for themes (ms_hrms_pwa_include_css). -->
			<header
				class="ms-app-header rounded-b-[32px] bg-brand-roots px-4 pb-5 pt-[max(20px,env(safe-area-inset-top))] text-brand-sand"
			>
				<div class="flex items-center gap-3">
					<router-link
						:to="{ name: 'Profile' }"
						:aria-label="__('Profile')"
						class="flex h-[46px] w-[46px] shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-brand-emerald text-[19px] font-bold text-brand-sand ring-2 ring-brand-mint/[.35]"
					>
						<img v-if="user.data?.user_image" :src="user.data.user_image" alt="" class="h-full w-full object-cover" />
						<span v-else>{{ initial }}</span>
					</router-link>
					<div class="min-w-0 grow">
						<div class="text-[13px] text-brand-sand/70">{{ greeting }}</div>
						<div class="truncate text-[20px] font-bold leading-snug">{{ employee.data?.employee_name }}</div>
					</div>
					<router-link
						:to="{ name: 'Notifications' }"
						:aria-label="__('Notifications')"
						class="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-brand-sand/[.08]"
					>
						<AppIcon name="bell" />
						<span
							v-if="unreadNotificationsCount.data"
							class="absolute end-[11px] top-[10px] h-[9px] w-[9px] rounded-full bg-brand-mint ring-2 ring-brand-roots"
						/>
					</router-link>
				</div>

				<div class="mt-3.5 flex items-center gap-1.5 text-[13px] text-brand-sand/70">
					<AppIcon name="calendar" :size="16" />
					<span class="truncate">{{ dateLine }}</span>
				</div>

				<CheckInPanel :now="now" :shift="home.data?.shift" class="mt-3.5" @logged="home.reload()" />
			</header>

			<router-link
				v-if="pending.length"
				:to="{ name: 'Approvals' }"
				class="ms-card mx-4 mt-4 flex items-center gap-3 px-3.5 py-3.5"
			>
				<span class="ms-icon-tile" :class="TONES.warning"><AppIcon name="users" /></span>
				<span class="min-w-0 grow">
					<span class="block text-[15px] font-bold text-brand-ink">
						{{ __("{0} requests await your approval", [pending.length]) }}
					</span>
					<span class="block truncate text-[12.5px] text-brand-muted">{{ pendingTypes }}</span>
				</span>
				<span class="flex shrink-0 -space-x-2 rtl:space-x-reverse">
					<span
						v-for="(name, index) in pendingPeople"
						:key="index"
						class="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white text-xs font-bold"
						:class="['bg-brand-emerald text-white', 'bg-brand-roots text-white', 'bg-brand-sand text-brand-roots'][index]"
					>
						{{ name }}
					</span>
				</span>
				<AppIcon name="forward" :size="20" class="text-brand-muted" />
			</router-link>

			<section class="mt-6 px-4" :aria-label="__('Quick actions')">
				<h2 class="ms-section-title mb-3">{{ __("Quick actions") }}</h2>
				<div class="grid grid-cols-4 gap-2">
					<router-link
						v-for="action in quickActions"
						:key="action.route"
						:to="{ name: action.route }"
						class="flex flex-col items-center gap-2 text-center text-[12.5px] font-semibold text-brand-ink"
					>
						<span class="flex h-[62px] w-[62px] items-center justify-center rounded-[20px] bg-white text-brand-emerald shadow-card">
							<AppIcon :name="action.icon" :size="24" />
						</span>
						{{ action.title }}
					</router-link>
				</div>
			</section>

			<section class="mt-7 px-4" :aria-label="__('Your month at a glance')">
				<div class="mb-2 flex items-center justify-between">
					<h2 class="ms-section-title">{{ __("Your month at a glance") }}</h2>
					<router-link :to="{ name: 'Insights' }" class="ms-link">
						{{ __("All insights") }}
						<AppIcon name="forward" :size="18" />
					</router-link>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<div class="ms-card row-span-2 flex flex-col items-center p-4 text-center">
						<div class="self-stretch text-start text-[13px] font-semibold text-brand-muted">{{ rate.title }}</div>
						<Ring :value="rate.value || 0" class="mt-3">
							<span class="text-[28px] font-bold leading-tight text-brand-ink">{{ rate.value ?? "–" }}{{ rate.value !== null ? "%" : "" }}</span>
							<span v-if="rate.delta" class="text-xs font-semibold" :class="rate.delta > 0 ? 'text-state-success-text' : 'text-state-danger-text'">
								{{ rate.delta > 0 ? "▲" : "▼" }} {{ Math.abs(rate.delta) }}
							</span>
						</Ring>
						<div class="mt-3 text-[13px] leading-6 text-brand-muted">{{ rate.caption }}</div>
					</div>

					<div class="ms-card p-3.5">
						<div class="flex items-center gap-1.5 text-[13px] font-semibold text-brand-muted">
							<AppIcon name="clock" :size="16" class="text-brand-emerald" />
							{{ __("Average arrival") }}
						</div>
						<div class="mt-2 text-[24px] font-bold text-brand-ink">{{ month?.avg_arrival ? clock(month.avg_arrival) : "–" }}</div>
						<div class="mt-0.5 text-xs font-semibold" :class="arrival.tone">{{ arrival.text }}</div>
					</div>

					<router-link :to="{ name: 'LeavesDashboard' }" class="ms-card block p-3.5">
						<span class="flex items-center gap-1.5 text-[13px] font-semibold text-brand-muted">
							<AppIcon name="sun" :size="16" class="text-brand-emerald" />
							{{ __("Leave Balance") }}
						</span>
						<template v-if="mainLeave">
							<span class="mt-2 block text-[24px] font-bold text-brand-ink">
								{{ formatNumber(mainLeave.balance_leaves) }}
								<span class="text-sm font-semibold text-brand-muted">{{ __("days") }}</span>
							</span>
							<span class="mt-2 block h-1.5 rounded-full bg-brand-emerald/[.12]">
								<span class="block h-full rounded-full bg-brand-emerald" :style="{ width: `${mainLeave.share}%` }" />
							</span>
						</template>
						<span v-else class="mt-2 block text-[13px] text-brand-muted">{{ __("No leave allocated") }}</span>
					</router-link>

					<div v-if="week" class="ms-card col-span-2 p-4">
						<div class="flex items-start justify-between gap-3">
							<div>
								<div class="text-[13px] font-semibold text-brand-muted">{{ __("Hours this week") }}</div>
								<div class="mt-1 text-[24px] font-bold text-brand-ink">
									{{ formatNumber(week.total, 1) }}
									<span class="text-sm font-semibold text-brand-muted">{{ __("of {0} h", [formatNumber(week.target, 1)]) }}</span>
								</div>
							</div>
						</div>
						<ColumnChart class="mt-4" :items="weekColumns" :target="weekTarget" />
					</div>
				</div>
			</section>

			<section v-if="notes.length" class="mt-7" :aria-label="__('Insights for you')">
				<h2 class="ms-section-title mx-4 mb-3">{{ __("Insights for you") }}</h2>
				<div class="hide-scrollbar flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1">
					<article
						v-for="(note, index) in notes"
						:key="index"
						class="w-[300px] shrink-0 snap-start rounded-[24px] p-[18px]"
						:class="index === 0 ? 'bg-brand-roots text-brand-sand' : 'bg-white text-brand-ink shadow-card'"
					>
						<div class="flex items-center gap-2.5">
							<span
								class="flex h-9 w-9 items-center justify-center rounded-xl"
								:class="index === 0 ? 'bg-brand-mint/[.16] text-brand-mint' : TONES[noteStyle(note).tone]"
							>
								<AppIcon :name="noteStyle(note).icon" :size="20" />
							</span>
							<span class="text-[13px] font-semibold" :class="index === 0 ? 'text-brand-mint' : 'text-brand-muted'">
								{{ noteStyle(note).title }}
							</span>
						</div>
						<p class="mt-3 text-[15px] leading-7">{{ note.text }}</p>
						<router-link
							v-if="note.action"
							:to="{ name: note.action.route }"
							class="mt-1 inline-flex min-h-[44px] items-center gap-1 text-sm font-semibold"
							:class="index === 0 ? 'text-brand-mint' : 'text-brand-emerald'"
						>
							{{ note.action.label }}
							<AppIcon name="forward" :size="18" />
						</router-link>
					</article>
				</div>
			</section>

			<section v-if="upcoming.length" class="mb-8 mt-7 px-4" :aria-label="__('Coming up')">
				<h2 class="ms-section-title mb-3">{{ __("Coming up") }}</h2>
				<div class="ms-card px-3.5">
					<component
						:is="item.to ? 'router-link' : 'div'"
						v-for="item in upcoming"
						:key="item.key"
						:to="item.to"
						class="ms-list-row"
					>
						<span class="ms-icon-tile flex-col bg-brand-sand leading-tight text-brand-emerald">
							<template v-if="item.day">
								<span class="text-base font-bold">{{ item.day }}</span>
								<span class="text-[10.5px] font-semibold">{{ item.month }}</span>
							</template>
							<AppIcon v-else :name="item.icon" />
						</span>
						<span class="min-w-0 grow">
							<span class="block truncate text-[15px] font-semibold text-brand-ink">{{ item.title }}</span>
							<span class="block truncate text-[12.5px] text-brand-muted">{{ item.subtitle }}</span>
						</span>
						<span v-if="item.chip" class="ms-chip" :class="item.chipTone">{{ item.chip }}</span>
					</component>
				</div>
			</section>
			<div v-else class="h-8" />
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue"
import {
	IonPage,
	IonContent,
	IonRefresher,
	IonRefresherContent,
	onIonViewDidEnter,
	onIonViewWillLeave,
} from "@ionic/vue"

import CheckInPanel from "@/components/CheckInPanel.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import Ring from "@/components/ui/Ring.vue"
import ColumnChart from "@/components/ui/ColumnChart.vue"

import { home, leaveOverview } from "@/data/pwa"
import { leaveBalance } from "@/data/leaves"
import { unreadNotificationsCount } from "@/data/notifications"
import { teamLeaves } from "@/data/leaves"
import { teamClaims } from "@/data/claims"
import {
	teamShiftRequests,
	teamAttendanceRequests,
	teamPermissionRequests,
	teamOvertimeRequests,
} from "@/data/attendance"
import { TONES, typeLabel } from "@/utils/requestTypes"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const user = inject("$user")
const employee = inject("$employee")

// The clock for the hours worked: it ticks only while this screen is shown.
const now = ref(dayjs())
let ticker = null
const startClock = () => {
	stopClock()
	now.value = dayjs()
	ticker = setInterval(() => (now.value = dayjs()), 1000)
}
const stopClock = () => ticker && clearInterval(ticker)
onIonViewDidEnter(startClock)
onIonViewWillLeave(stopClock)
onMounted(startClock)
onBeforeUnmount(stopClock)

onMounted(() => {
	home.reload()
	leaveOverview.reload()
})

const teamSources = [
	teamLeaves,
	teamClaims,
	teamPermissionRequests,
	teamOvertimeRequests,
	teamShiftRequests,
	teamAttendanceRequests,
]

async function refresh(event) {
	await Promise.allSettled([home.reload(), leaveBalance.reload(), leaveOverview.reload(), ...teamSources.map((r) => r.reload())])
	event.target.complete()
}

const initial = computed(() => Array.from(employee.data?.employee_name || user.data?.first_name || "?")[0])
const greeting = computed(() => (now.value.hour() < 12 ? __("Good morning") : __("Good evening")))
const clock = (time) => dayjs(`2000-01-01 ${time}`).format("h:mm a")

const dateLine = computed(() => {
	const parts = [dayjs().format("dddd D MMMM")]
	const shift = home.data?.shift
	if (shift) parts.push(`${__(shift.name)} ${clock(shift.start)} – ${clock(shift.end)}`)
	return parts.join(" · ")
})

// Approvals
const pending = computed(() => teamSources.flatMap((resource) => resource.data || []))
const pendingTypes = computed(() =>
	[...new Set(pending.value.map((doc) => doc.doctype))].map(typeLabel).join(" · ")
)
const pendingPeople = computed(() =>
	[...new Set(pending.value.map((doc) => doc.employee_name))].slice(0, 3).map((name) => Array.from(name || "?")[0])
)

const quickActions = [
	{ icon: "sun", title: __("Request Leave"), route: "LeaveApplicationFormView" },
	{ icon: "hourglass", title: __("Permission Request"), route: "PermissionRequestNewView" },
	{ icon: "clock-plus", title: __("Overtime"), route: "OvertimeRequestNewView" },
	{ icon: "receipt", title: __("Expenses"), route: "ExpenseClaimFormView" },
]

// Month
const month = computed(() => home.data?.month)
const previous = computed(() => home.data?.previous_month)

const rate = computed(() => {
	const current = month.value
	if (!current) return { title: __("Punctuality"), value: null, caption: "" }
	if (current.punctuality !== null && current.punctuality !== undefined) {
		const before = previous.value?.punctuality
		return {
			title: __("Punctuality"),
			value: current.punctuality,
			delta: before !== null && before !== undefined ? current.punctuality - before : 0,
			caption: __("{0} of {1} days on time", [current.on_time, current.judged]),
		}
	}
	return {
		title: __("Attendance rate"),
		value: current.attendance_rate,
		delta: 0,
		caption: current.expected ? __("{0} of {1} days present", [current.present, current.expected]) : __("No working days yet"),
	}
})

const minutesOf = (time) => {
	const [h, m] = time.split(":").map(Number)
	return h * 60 + m
}

const arrival = computed(() => {
	const current = month.value?.avg_arrival
	const before = previous.value?.avg_arrival
	if (!current) return { text: __("No check-ins this month"), tone: "text-brand-muted" }
	if (!before) return { text: __("This month"), tone: "text-brand-muted" }
	const difference = minutesOf(before) - minutesOf(current)
	const lastMonth = dayjs().subtract(1, "month").format("MMMM")
	if (difference > 0) return { text: __("{0} min earlier than {1}", [difference, lastMonth]), tone: "text-state-success-text" }
	if (difference < 0)
		return { text: __("{0} min later than {1}", [-difference, lastMonth]), tone: "text-state-warning-text" }
	return { text: __("Same as {0}", [lastMonth]), tone: "text-brand-muted" }
})

const mainLeave = computed(() => {
	const balances = Object.values(leaveBalance.data || {})
	if (!balances.length) return null
	const main = balances.reduce((a, b) => (b.allocated_leaves > a.allocated_leaves ? b : a))
	return { ...main, share: Math.min((main.balance_leaves / (main.allocated_leaves || 1)) * 100, 100) }
})

const week = computed(() => home.data?.week)
const weekColumns = computed(() =>
	(week.value?.days || []).map((day) => ({
		key: day.date,
		label: day.is_today ? __("Today") : dayjs(day.date).format("ddd"),
		value: day.hours,
		display: day.hours ? __("{0} h", [formatNumber(day.hours, 1)]) : "",
		accent: day.is_today,
	}))
)
const weekTarget = computed(() => {
	const shift = home.data?.shift
	if (!shift) return null
	const hours = (minutesOf(shift.end) - minutesOf(shift.start) + 1440) % 1440 / 60
	return hours ? { value: hours, label: __("{0} h", [formatNumber(hours, 1)]) } : null
})

// Insights
const notes = computed(() => home.data?.insights || [])
const NOTE_STYLES = {
	leave: { icon: "bulb", tone: "emerald", title: __("Leave reminder") },
	attendance: { icon: "clock", tone: "warning", title: __("Attendance pattern") },
	warning: { icon: "alert", tone: "danger", title: __("Needs attention") },
	positive: { icon: "trend-up", tone: "success", title: __("Well done") },
	info: { icon: "clock-plus", tone: "info", title: __("Overtime") },
}
const noteStyle = (note) => NOTE_STYLES[note.kind] || NOTE_STYLES.info

// Coming up
const upcoming = computed(() => {
	const items = []
	const holiday = home.data?.next_holiday
	if (holiday) {
		const date = dayjs(holiday.date)
		items.push({
			key: "holiday",
			day: date.format("D"),
			month: date.format("MMM"),
			title: __(holiday.description),
			subtitle: `${__("Public holiday")} · ${date.format("dddd")}`,
			chip: holiday.days_left === 0 ? __("Today") : holiday.days_left === 1 ? __("Tomorrow") : __("In {0} days", [holiday.days_left]),
			chipTone: TONES.roots,
		})
	}
	const leave = leaveOverview.data?.mine?.[0]
	if (leave) {
		const from = dayjs(leave.from_date)
		items.push({
			key: "leave",
			day: from.format("D"),
			month: from.format("MMM"),
			title: __(leave.leave_type, null, "Leave Type"),
			subtitle: leave.from_date === leave.to_date ? from.format("dddd") : `${from.format("D MMM")} – ${dayjs(leave.to_date).format("D MMM")}`,
			chip: __(leave.status, null, "Leave Application"),
			chipTone: leave.status === "Approved" ? TONES.success : TONES.warning,
			to: { name: "LeaveApplicationDetailView", params: { id: leave.name } },
		})
	}
	const slip = home.data?.latest_salary_slip
	if (slip && dayjs().diff(dayjs(slip.posting_date), "day") <= 40) {
		items.push({
			key: "slip",
			icon: "file",
			title: __("Salary slip for {0} is ready", [dayjs(slip.end_date).format("MMMM")]),
			subtitle: __("Tap to view or download it"),
			chip: __("New"),
			chipTone: TONES.info,
			to: { name: "SalarySlipDetailView", params: { id: slip.name } },
		})
	}
	return items
})
</script>
