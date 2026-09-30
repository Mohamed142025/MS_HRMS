<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('Leave Balance')" :subtitle="__('Year {0}', [dayjs().year()])" fallback="/requests">
				<template #actions>
					<router-link :to="{ name: 'LeaveApplicationListView' }" class="ms-icon-button" :aria-label="__('View Leave History')">
						<AppIcon name="clipboard" :size="20" />
					</router-link>
				</template>
			</SubHeader>

			<template v-if="types.length">
				<section class="ms-card mx-4 mt-4 p-[18px]" :aria-label="main.type">
					<div class="text-[14px] font-bold text-brand-ink">{{ __(main.type, null, "Leave Type") }}</div>
					<div class="mt-3 flex items-center gap-4">
						<Ring :value="main.share" :size="140" :stroke="11">
							<span class="text-[30px] font-bold leading-tight text-brand-ink">{{ formatNumber(main.remaining) }}</span>
							<span class="text-[12.5px] text-brand-muted">{{ __("days left") }}</span>
						</Ring>
						<dl class="flex grow flex-col gap-2.5 text-[13.5px]">
							<div v-for="row in main.rows" :key="row.label" class="flex items-center justify-between gap-2">
								<dt class="inline-flex items-center gap-1.5 text-brand-ink/80">
									<span class="h-2.5 w-2.5 rounded-[3px]" :class="row.swatch" />
									{{ row.label }}
								</dt>
								<dd class="font-bold text-brand-ink">{{ formatNumber(row.value) }}</dd>
							</div>
							<div class="flex items-center justify-between gap-2 border-t border-brand-roots/[.08] pt-2.5 text-brand-muted">
								<dt>{{ __("Allocated days") }}</dt>
								<dd class="font-bold text-brand-ink">{{ formatNumber(main.total) }}</dd>
							</div>
						</dl>
					</div>
					<div v-if="main.expiry" class="mt-3.5 flex items-start gap-2 rounded-2xl bg-state-warning/[.12] px-3 py-2.5 text-[13px] leading-6 text-state-warning-text">
						<AppIcon name="clock" :size="18" class="mt-0.5 shrink-0" />
						{{ main.expiry }}
					</div>
				</section>

				<section v-if="others.length" class="mx-4 mt-3 grid grid-cols-2 gap-3" :aria-label="__('Other leave types')">
					<div v-for="type in others" :key="type.type" class="ms-card p-3.5">
						<div class="truncate text-[13px] font-semibold text-brand-muted">{{ __(type.type, null, "Leave Type") }}</div>
						<div class="mt-1.5 text-[22px] font-bold text-brand-ink">
							{{ formatNumber(type.remaining) }}
							<span class="text-[13px] font-semibold text-brand-muted">{{ __("of {0}", [formatNumber(type.total)]) }}</span>
						</div>
						<div class="mt-2 h-1.5 rounded-full bg-brand-emerald/[.12]">
							<div class="h-full rounded-full bg-brand-emerald" :style="{ width: `${type.share}%` }" />
						</div>
					</div>
				</section>
			</template>
			<div v-else-if="leaveOverview.data" class="ms-caption mx-4 mt-4 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center">
				{{ __("You have no leaves allocated") }}
			</div>

			<section v-if="upcomingLeaves.length" class="ms-card mx-4 mt-3 px-4 pb-1 pt-4" :aria-label="upcomingTitle">
				<h2 class="text-[15.5px] font-bold text-brand-ink">{{ upcomingTitle }}</h2>
				<div v-if="leaveOverview.data?.department" class="ms-caption">{{ __("Plan your leave around your colleagues'") }}</div>
				<div v-for="leave in upcomingLeaves" :key="`${leave.employee}${leave.from_date}`" class="ms-list-row">
					<span
						class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full text-[15px] font-bold"
						:class="leave.mine ? 'bg-brand-emerald text-white' : 'bg-brand-roots/[.08] text-brand-roots'"
					>
						{{ Array.from(leave.employee_name || "?")[0] }}
					</span>
					<span class="min-w-0 grow">
						<span class="block truncate text-[14.5px] font-semibold text-brand-ink">{{ leave.mine ? __("You") : leave.employee_name }}</span>
						<span class="block truncate text-[12.5px] text-brand-muted">{{ dates(leave) }}</span>
					</span>
					<StatusChip :status="leave.status === 'Open' ? 'Pending' : leave.status" />
				</div>
			</section>

			<section v-if="upcomingHolidays.length" class="ms-card mx-4 mt-3 px-4 pb-1 pt-4" :aria-label="__('Upcoming Holidays')">
				<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Upcoming Holidays") }}</h2>
				<div v-for="holiday in upcomingHolidays" :key="holiday.date" class="ms-list-row">
					<span class="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-[14px] bg-brand-roots leading-tight text-brand-sand">
						<span class="text-lg font-bold">{{ dayjs(holiday.date).format("D") }}</span>
						<span class="text-[10.5px] font-semibold text-brand-mint">{{ dayjs(holiday.date).format("MMM") }}</span>
					</span>
					<span class="min-w-0 grow">
						<span class="block truncate text-[15px] font-semibold text-brand-ink">{{ __(holiday.description) }}</span>
						<span class="block text-[12.5px] text-brand-muted">
							{{ dayjs(holiday.date).format("dddd") }} · {{ inDays(holiday.date) }}
						</span>
					</span>
				</div>
			</section>

			<div class="h-6" />
		</ion-content>

		<ion-footer class="ion-no-border">
			<div class="border-t border-brand-roots/[.08] bg-white px-4 pb-[max(20px,env(safe-area-inset-bottom))] pt-3.5">
				<router-link :to="{ name: 'LeaveApplicationFormView' }" class="ms-primary-button">
					<AppIcon name="plus" :size="20" :stroke-width="2.2" />
					{{ __("Request Leave") }}
				</router-link>
			</div>
		</ion-footer>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"
import { IonPage, IonContent, IonFooter } from "@ionic/vue"

import SubHeader from "@/components/ui/SubHeader.vue"
import Ring from "@/components/ui/Ring.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import StatusChip from "@/components/ui/StatusChip.vue"

import { leaveOverview } from "@/data/pwa"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

onMounted(() => leaveOverview.reload())

const types = computed(() =>
	Object.entries(leaveOverview.data?.balances || {})
		.map(([type, balance]) => ({
			type,
			total: balance.total_leaves,
			used: balance.leaves_taken,
			pending: balance.leaves_pending_approval,
			expired: balance.expired_leaves,
			remaining: balance.remaining_leaves,
			share: Math.min((balance.remaining_leaves / (balance.total_leaves || 1)) * 100, 100),
		}))
		.sort((a, b) => b.total - a.total)
)

const main = computed(() => {
	const type = types.value[0]
	const allocation = leaveOverview.data?.allocations?.[type.type]
	let expiry = ""
	if (allocation && !allocation.carry_forward && type.remaining > 0) {
		const end = dayjs(allocation.to_date)
		if (end.diff(dayjs(), "day") <= 90)
			expiry = __("{0} days expire on {1} if not used", [formatNumber(type.remaining), end.format("D MMMM")])
	}
	return {
		...type,
		expiry,
		rows: [
			{ label: __("Remaining"), value: type.remaining, swatch: "bg-brand-emerald" },
			{ label: __("Used"), value: type.used, swatch: "bg-brand-emerald/[.12]" },
			...(type.pending ? [{ label: __("Pending approval"), value: type.pending, swatch: "bg-state-warning/[.28]" }] : []),
			...(type.expired ? [{ label: __("Expired"), value: type.expired, swatch: "bg-brand-roots/[.18]" }] : []),
		],
	}
})
const others = computed(() => types.value.slice(1))

const upcomingTitle = computed(() =>
	leaveOverview.data?.department ? __("Upcoming leaves in your department") : __("Your upcoming leaves")
)
const upcomingLeaves = computed(() =>
	[
		...(leaveOverview.data?.mine || []).map((leave) => ({ ...leave, mine: true })),
		...(leaveOverview.data?.department || []),
	].sort((a, b) => (a.from_date < b.from_date ? -1 : 1))
)
const dates = (leave) =>
	leave.from_date === leave.to_date
		? dayjs(leave.from_date).format("dddd D MMMM")
		: `${dayjs(leave.from_date).format("D MMM")} – ${dayjs(leave.to_date).format("D MMM")}`

const upcomingHolidays = computed(() => leaveOverview.data?.holidays || [])
const inDays = (date) => {
	const days = dayjs(date).startOf("day").diff(dayjs().startOf("day"), "day")
	if (days === 0) return __("Today")
	if (days === 1) return __("Tomorrow")
	return __("In {0} days", [days])
}
</script>
