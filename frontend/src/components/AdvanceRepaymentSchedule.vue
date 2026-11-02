<template>
	<!-- An approved advance's repayment plan, as HR set it: what is repaid, what is left,
	     and each month's installment with where it stands. -->
	<section v-if="rows.length" class="ms-card mx-4 mt-3 p-4">
		<div class="flex items-center justify-between gap-3">
			<h2 class="ms-section-title">{{ __("Repayment Plan") }}</h2>
			<span class="ms-caption">{{ __("{0} of {1} months", [deducted.length, rows.length]) }}</span>
		</div>

		<p v-if="waitingForPayment" class="mt-2 rounded-2xl bg-state-info/[.12] px-3 py-2 text-[13px] text-state-info-text">
			{{ __("Deductions start once the advance is paid to you.") }}
		</p>
		<div class="mt-3 grid grid-cols-2 gap-2.5">
			<div class="rounded-2xl bg-brand-sand/60 px-3 py-2.5">
				<p class="ms-caption">{{ __("Repaid From Salary") }}</p>
				<p class="mt-0.5 text-[17px] font-bold text-brand-ink">{{ money(repaid) }}</p>
			</div>
			<div class="rounded-2xl bg-brand-sand/60 px-3 py-2.5">
				<p class="ms-caption">{{ __("Remaining to Repay") }}</p>
				<p class="mt-0.5 text-[17px] font-bold text-brand-ink">{{ money(total - repaid) }}</p>
			</div>
		</div>
		<div class="mt-3 h-2 overflow-hidden rounded-full bg-brand-sand" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
			<div class="h-full rounded-full bg-brand-emerald transition-all" :style="{ width: `${progress}%` }" />
		</div>

		<ul class="mt-4 flex flex-col divide-y divide-brand-roots/[.08]">
			<li v-for="row in rows" :key="row.name" class="flex items-center gap-3 py-3">
				<div class="min-w-0 grow">
					<p class="text-[15px] font-semibold text-brand-ink">{{ monthLabel(row.payroll_date) }}</p>
					<p v-if="row.status === 'Missed'" class="ms-caption">{{ __("Not deducted this month") }}</p>
					<p v-else-if="row.status === 'Scheduled' && row.note" class="ms-caption">{{ __("Rescheduled") }}</p>
				</div>
				<span class="shrink-0 text-[15px] font-semibold text-brand-ink" dir="ltr">{{ money(row.amount) }}</span>
				<StatusChip :status="row.status" :label="__(STATUS_LABELS[row.status] || row.status)" />
			</li>
		</ul>
	</section>
</template>

<script setup>
import { computed, inject } from "vue"

import StatusChip from "@/components/ui/StatusChip.vue"
import dayjs from "@/utils/dayjs"
import { formatCurrency } from "@/utils/formatters"

const __ = inject("$translate")

const props = defineProps({
	advance: { type: Object, required: true },
})

const STATUS_LABELS = {
	Scheduled: "Upcoming",
	Due: "Due This Month",
	Deducted: "Deducted",
	Missed: "Missed",
}

const rows = computed(() =>
	[...(props.advance.custom_repayment_schedule || [])].sort((a, b) => (a.payroll_date > b.payroll_date ? 1 : -1))
)
const deducted = computed(() => rows.value.filter((row) => row.status === "Deducted"))
const total = computed(() => rows.value.reduce((sum, row) => sum + Number(row.amount || 0), 0))
const repaid = computed(() => deducted.value.reduce((sum, row) => sum + Number(row.amount || 0), 0))
const progress = computed(() => (total.value ? Math.round((repaid.value / total.value) * 100) : 0))

// Nothing is deducted before the advance is paid (its amounts reach this form formatted,
// so its status tells).
const waitingForPayment = computed(
	() => props.advance.status === "Unpaid" && rows.value.some((row) => row.status === "Scheduled")
)
const money = (value) => formatCurrency(value, props.advance.currency)

const monthLabel = (date) => dayjs(date).format("MMMM YYYY")
</script>
