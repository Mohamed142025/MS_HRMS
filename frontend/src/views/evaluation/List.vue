<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('My Evaluations')" :subtitle="__('Only you can see them')" fallback="/profile" />

			<div v-if="evaluations.loading && !evaluations.data" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<div
				v-else-if="!evaluations.data?.length"
				class="ms-caption mx-4 mt-4 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center"
			>
				{{ __("Your evaluations show here once HR approves them.") }}
			</div>
			<template v-else>
				<section v-if="trend.length > 1" class="ms-card mx-4 mt-4 p-4" :aria-label="__('Your scores')">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Your scores") }}</h2>
					<LineChart class="mt-3" :points="trend" />
				</section>

				<div class="mx-4 mb-8 mt-3 flex flex-col gap-2.5">
					<router-link
						v-for="(row, index) in evaluations.data"
						:key="row.name"
						:to="{ name: 'EmployeeEvaluationDetailView', params: { id: row.name } }"
						class="ms-card flex items-center gap-3.5 p-3.5"
					>
						<Ring :value="row.final_score" :size="58" :stroke="11">
							<span class="text-[15px] font-bold text-brand-ink">{{ score(row.final_score) }}</span>
						</Ring>
						<span class="min-w-0 grow">
							<span class="block truncate text-[15px] font-bold text-brand-ink">{{ period(row) }}</span>
							<span class="block text-[13px] text-brand-muted">
								{{ __("Incentive {0}", [formatCurrency(row.incentive_amount, row.currency)]) }}
							</span>
							<span v-if="!row.acknowledged_on" class="ms-chip mt-1 bg-state-info/[.12] text-state-info-text">{{ __("New") }}</span>
						</span>
						<span v-if="change(index) !== null" class="shrink-0 text-[13px] font-bold" :class="change(index) >= 0 ? 'text-state-success-text' : 'text-state-danger-text'" dir="ltr">
							{{ change(index) >= 0 ? "↑" : "↓" }} {{ Math.abs(change(index)) }}
						</span>
						<AppIcon name="forward" :size="18" class="shrink-0 text-brand-muted" />
					</router-link>
				</div>
			</template>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { IonPage, IonContent, onIonViewWillEnter } from "@ionic/vue"
import { createResource } from "frappe-ui"

import SubHeader from "@/components/ui/SubHeader.vue"
import Ring from "@/components/ui/Ring.vue"
import LineChart from "@/components/ui/LineChart.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { formatCurrency } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const evaluations = createResource({ url: "ms_hrms.my_evaluations.get_my_evaluations" })
onIonViewWillEnter(() => evaluations.reload())

const score = (value) => `${Math.round(value || 0)}%`
const period = (row) => `${dayjs(row.from_date).format("D MMM")} – ${dayjs(row.to_date).format("D MMM YYYY")}`

// Against the period before (the list is newest first).
function change(index) {
	const rows = evaluations.data || []
	if (index + 1 >= rows.length) return null
	return Math.round((rows[index].final_score || 0) - (rows[index + 1].final_score || 0))
}

const trend = computed(() =>
	[...(evaluations.data || [])]
		.slice(0, 6)
		.reverse()
		.map((row) => ({ label: dayjs(row.to_date).format("MMM"), value: row.final_score, display: score(row.final_score) }))
)
</script>
