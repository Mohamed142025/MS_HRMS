<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<FinanceHeader current="salary" />

			<template v-if="latest">
				<section class="ms-dark-card mx-4 mt-4 p-5" :aria-label="__('Net pay')">
					<div class="flex items-center justify-between gap-2">
						<span class="text-[13.5px] text-brand-sand/70">{{ __("Net pay for {0}", [monthName(latest)]) }}</span>
						<span class="ms-chip bg-brand-mint/[.12] text-brand-mint">{{ __("Issued", null, "Salary Slip") }}</span>
					</div>
					<div class="mt-2 flex items-baseline gap-2">
						<span class="text-[40px] font-bold leading-tight">{{ amount(latest.net_pay) }}</span>
						<span class="text-base font-semibold text-brand-sand/70">{{ __(latest.currency) }}</span>
					</div>
					<div class="mt-1 text-[13px] text-brand-sand/70">{{ __("Issued on {0}", [dayjs(latest.posting_date).format("D MMMM YYYY")]) }}</div>
					<div class="mt-4 grid grid-cols-2 gap-2">
						<div class="rounded-2xl bg-brand-sand/[.06] px-3 py-2.5">
							<div class="text-xs text-brand-sand/70">{{ __("Gross Pay") }}</div>
							<div class="text-base font-bold">{{ amount(latest.gross_pay) }}</div>
						</div>
						<div class="rounded-2xl bg-brand-sand/[.06] px-3 py-2.5">
							<div class="text-xs text-brand-sand/70">{{ __("Total Deduction") }}</div>
							<div class="text-base font-bold">{{ amount(latest.total_deduction) }}</div>
						</div>
					</div>
					<div class="mt-3.5 flex gap-2">
						<router-link
							:to="{ name: 'SalarySlipDetailView', params: { id: latest.name } }"
							class="flex h-12 grow items-center justify-center rounded-[14px] bg-brand-mint text-[15px] font-bold text-brand-roots"
						>
							{{ __("View slip") }}
						</router-link>
						<button
							type="button"
							class="flex h-12 w-12 items-center justify-center rounded-[14px] border border-brand-sand/[.28] text-brand-sand disabled:opacity-60"
							:aria-label="__('Download PDF')"
							:disabled="downloading"
							@click="download(latest.name)"
						>
							<AppIcon name="download" :size="20" />
						</button>
					</div>
				</section>

				<section v-if="trend.length > 1" class="ms-card mx-4 mt-3 p-4" :aria-label="__('Net pay')">
					<div class="flex items-start justify-between gap-2">
						<div>
							<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Net pay") }}</h2>
							<div class="ms-caption">{{ __("Last {0} slips · average {1}", [trend.length, amount(average)]) }}</div>
						</div>
						<div class="text-end">
							<div class="text-[13px] font-semibold text-brand-muted">{{ __("This year") }}</div>
							<div class="text-[15px] font-bold text-brand-ink">{{ amount(salary.data.year_net_pay) }}</div>
						</div>
					</div>
					<ColumnChart class="mt-4" :items="trend" :height="100" :bar-width="24" />
				</section>

				<section v-if="earnings.length" class="ms-card mx-4 mt-3 p-4" :aria-label="__('Salary breakdown')">
					<h2 class="mb-3.5 text-[15.5px] font-bold text-brand-ink">{{ __("Salary breakdown for {0}", [monthName(latest)]) }}</h2>
					<BarList :rows="earnings" />
					<div class="mt-3.5 flex items-center justify-between border-t border-brand-roots/[.08] pt-3 text-[14px] text-state-danger-text">
						<span>{{ __("Deductions") }}</span>
						<span class="font-bold" dir="ltr">−{{ amount(latest.total_deduction) }}</span>
					</div>
				</section>

				<section v-if="salary.data.slips.length > 1" class="mx-4 mb-8 mt-5" :aria-label="__('Previous slips')">
					<h2 class="ms-group-title mb-2.5">{{ __("Previous slips") }}</h2>
					<div class="ms-card px-3.5">
						<router-link
							v-for="slip in salary.data.slips.slice(1)"
							:key="slip.name"
							:to="{ name: 'SalarySlipDetailView', params: { id: slip.name } }"
							class="ms-list-row"
						>
							<span class="ms-icon-tile h-10 w-10 bg-brand-sand text-brand-emerald"><AppIcon name="file" :size="20" /></span>
							<span class="grow text-[15px] font-semibold text-brand-ink">{{ monthName(slip, true) }}</span>
							<span class="text-[15px] font-bold text-brand-ink">{{ amount(slip.net_pay) }}</span>
							<AppIcon name="forward" :size="18" class="text-brand-muted" />
						</router-link>
					</div>
				</section>
				<div v-else class="h-8" />
			</template>
			<div
				v-else-if="salary.data"
				class="ms-caption mx-4 mt-5 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center"
			>
				{{ __("No salary slips found") }}
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted, onBeforeUnmount } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"

import FinanceHeader from "@/components/FinanceHeader.vue"
import ColumnChart from "@/components/ui/ColumnChart.vue"
import BarList from "@/components/ui/BarList.vue"
import AppIcon from "@/components/ui/AppIcon.vue"

import { salary } from "@/data/pwa"
import { privacy } from "@/data/ui"
import { formatNumber } from "@/utils/formatters"
import { useSalarySlipDownload } from "@/composables/salarySlip"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const employee = inject("$employee")

const { download, downloading } = useSalarySlipDownload()

onMounted(() => salary.reload())

async function refresh(event) {
	await salary.reload()
	event.target.complete()
}

const latest = computed(() => salary.data?.slips?.length && salary.data.latest)
const amount = (value) => (privacy.hidden ? "••••" : formatNumber(value, 0))

// A slip is named by its month, or its range when it covers more than one.
const monthName = (slip, withYear = false) => {
	const start = dayjs(slip.start_date)
	const end = dayjs(slip.end_date)
	if (start.isSame(end, "month")) return end.format(withYear ? "MMMM YYYY" : "MMMM")
	return `${start.format("MMM")} – ${end.format(withYear ? "MMM YYYY" : "MMM")}`
}

const trend = computed(() =>
	(salary.data?.slips || [])
		.slice(0, 6)
		.reverse()
		.map((slip, index, list) => ({
			key: slip.name,
			label: dayjs(slip.end_date).format("MMM"),
			value: slip.net_pay,
			display: amount(slip.net_pay),
			accent: index === list.length - 1,
		}))
)
const average = computed(() => trend.value.reduce((sum, item) => sum + item.value, 0) / (trend.value.length || 1))

const earnings = computed(() =>
	(salary.data?.latest?.earnings || [])
		.slice()
		.sort((a, b) => b.amount - a.amount)
		.map((row) => ({ label: __(row.component), value: row.amount, display: amount(row.amount) }))
)

function onSalarySlips(data) {
	if (data.employee === employee.data.name) salary.reload()
}
onMounted(() => socket.on("hrms:update_salary_slips", onSalarySlips))
onBeforeUnmount(() => socket.off("hrms:update_salary_slips", onSalarySlips))
</script>
