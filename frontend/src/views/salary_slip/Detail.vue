<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="title" :subtitle="props.id" fallback="/dashboard/salary-slips">
				<template #actions>
					<button
						type="button"
						class="ms-icon-button"
						:aria-label="privacy.hidden ? __('Show amounts') : __('Hide amounts')"
						:aria-pressed="privacy.hidden"
						@click="privacy.toggle()"
					>
						<AppIcon :name="privacy.hidden ? 'eye-off' : 'eye'" :size="20" />
					</button>
				</template>
			</SubHeader>

			<div v-if="!slip" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<template v-else>
				<section class="ms-card mx-4 mt-4 grid grid-cols-3 gap-2 p-3 text-center" :aria-label="__('Details')">
					<div v-for="item in facts" :key="item.label" class="rounded-2xl bg-brand-sand px-1 py-2.5">
						<div class="text-xs text-brand-muted">{{ item.label }}</div>
						<div class="text-[14px] font-bold text-brand-ink">{{ item.value }}</div>
					</div>
				</section>

				<section v-for="part in parts" :key="part.title" class="ms-card mx-4 mt-3 p-4" :aria-label="part.title">
					<div class="flex items-center justify-between">
						<h2 class="text-[15.5px] font-bold text-brand-ink">{{ part.title }}</h2>
						<span class="ms-chip" :class="part.tone">
							<bdi dir="ltr">{{ part.sign }}{{ amount(part.total) }}</bdi> {{ __(slip.currency) }}
						</span>
					</div>
					<div class="mt-1.5 flex flex-col">
						<div
							v-for="row in part.rows"
							:key="row.name"
							class="flex justify-between gap-3 border-b border-brand-roots/[.08] py-2.5 text-[14.5px] last:border-b-0"
						>
							<span class="text-brand-ink">{{ __(row.salary_component) }}</span>
							<span class="font-semibold text-brand-ink">{{ amount(row.amount) }}</span>
						</div>
						<div v-if="!part.rows.length" class="ms-caption py-2">{{ __("None") }}</div>
					</div>
				</section>

				<section class="ms-dark-card mx-4 mb-6 mt-3 p-[18px]" :aria-label="__('Net Pay')">
					<div class="flex items-center justify-between gap-3">
						<span class="text-[14px] text-brand-sand/70">{{ __("Net Pay") }}</span>
						<span class="flex items-baseline gap-1.5">
							<span class="text-[30px] font-bold">{{ amount(slip.net_pay) }}</span>
							<span class="text-sm text-brand-sand/70">{{ __(slip.currency) }}</span>
						</span>
					</div>
				</section>
			</template>
		</ion-content>

		<ion-footer class="ion-no-border">
			<div class="border-t border-brand-roots/[.08] bg-white px-4 pb-[max(20px,env(safe-area-inset-bottom))] pt-3.5">
				<button type="button" class="ms-primary-button" :disabled="downloading || !slip" @click="download(props.id)">
					<AppIcon name="download" :size="20" :stroke-width="2" />
					{{ __("Download PDF") }}
				</button>
			</div>
		</ion-footer>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { IonPage, IonContent, IonFooter } from "@ionic/vue"
import { createDocumentResource } from "frappe-ui"

import SubHeader from "@/components/ui/SubHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"

import { privacy } from "@/data/ui"
import { formatNumber } from "@/utils/formatters"
import { useSalarySlipDownload } from "@/composables/salarySlip"

const props = defineProps({
	id: { type: String, required: true },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const { download, downloading } = useSalarySlipDownload()

const document = createDocumentResource({ doctype: "Salary Slip", name: props.id, auto: true })
const slip = computed(() => document.doc)

const amount = (value) => (privacy.hidden ? "••••" : formatNumber(value, 2))

const title = computed(() => {
	if (!slip.value) return __("Salary Slip")
	const start = dayjs(slip.value.start_date)
	const end = dayjs(slip.value.end_date)
	const period = start.isSame(end, "month") ? end.format("MMMM YYYY") : `${start.format("MMM")} – ${end.format("MMM YYYY")}`
	return __("Salary slip for {0}", [period])
})

const facts = computed(() => [
	{ label: __("Period"), value: `${dayjs(slip.value.start_date).format("D MMM")} – ${dayjs(slip.value.end_date).format("D MMM")}` },
	{ label: __("Payment Days"), value: formatNumber(slip.value.payment_days, 1) },
	{ label: __("Issue date"), value: dayjs(slip.value.posting_date).format("D MMM YYYY") },
])

const parts = computed(() => [
	{
		title: __("Earnings"),
		rows: (slip.value.earnings || []).filter((row) => row.amount),
		total: slip.value.gross_pay,
		sign: "+",
		tone: "bg-state-success/[.12] text-state-success-text",
	},
	{
		title: __("Deductions"),
		rows: (slip.value.deductions || []).filter((row) => row.amount),
		total: slip.value.total_deduction,
		sign: "−",
		tone: "bg-state-danger/[.12] text-state-danger-text",
	},
])
</script>
