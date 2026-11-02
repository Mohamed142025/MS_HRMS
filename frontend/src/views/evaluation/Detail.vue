<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('My Evaluation')" :subtitle="data ? period : ''" :fallback="{ name: 'EmployeeEvaluationListView' }" />

			<div v-if="evaluation.error" class="ms-caption p-10 text-center">{{ evaluation.error.messages?.[0] || __("This evaluation is not yours to see.") }}</div>
			<div v-else-if="!data" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<template v-else>
				<!-- The result -->
				<section class="ms-dark-card mx-4 mt-4 p-[18px]" :aria-label="__('Final score')">
					<div class="flex items-center gap-4">
						<Ring :value="data.final_score" :size="124" :stroke="10" color-class="text-brand-mint" track-class="text-brand-sand/[.12]">
							<span class="text-[34px] font-bold leading-none">{{ score(data.final_score) }}</span>
							<span class="mt-1 text-xs text-brand-sand/70">{{ __("Final score") }}</span>
						</Ring>
						<div class="min-w-0">
							<div v-if="change !== null" class="text-[14px] font-bold" :class="change >= 0 ? 'text-brand-mint' : 'text-[#fca5a5]'">
								{{ change >= 0 ? __("Up {0} points on last time", [change]) : __("Down {0} points on last time", [-change]) }}
							</div>
							<div v-if="data.evaluator_name" class="mt-1 text-[13px] text-brand-sand/70">{{ __("Evaluated by {0}", [data.evaluator_name]) }}</div>
						</div>
					</div>
					<div class="mt-4 grid grid-cols-2 gap-2">
						<div class="rounded-2xl bg-brand-sand/[.06] px-3 py-2.5">
							<div class="text-lg font-bold">{{ formatCurrency(data.incentive_amount, data.currency) }}</div>
							<div class="text-xs text-brand-sand/70">{{ __("Your incentive") }}</div>
						</div>
						<div class="rounded-2xl bg-brand-sand/[.06] px-3 py-2.5">
							<div class="text-lg font-bold">{{ score(data.incentive_percent) }}</div>
							<div class="text-xs text-brand-sand/70">{{ __("Of the incentive amount") }}</div>
						</div>
					</div>
					<p v-if="data.incentive_amount > 0" class="mt-3 text-xs leading-5 text-brand-sand/60">{{ __("Paid with this period's salary.") }}</p>
				</section>

				<!-- The parts and their items -->
				<section v-for="part in data.parts" :key="part.name" class="ms-card mx-4 mt-3 p-4" :aria-label="part.name">
					<div class="flex items-center justify-between gap-3">
						<h2 class="text-[15.5px] font-bold text-brand-ink">{{ part.name }}</h2>
						<span class="shrink-0 text-[15px] font-bold text-brand-ink" dir="ltr">{{ points(part.score) }} / {{ points(part.weight) }}</span>
					</div>
					<div class="mt-2 h-2 overflow-hidden rounded-full bg-brand-sand">
						<div class="h-full rounded-full bg-brand-emerald" :style="{ width: `${share(part.score, part.weight)}%` }" />
					</div>
					<ul class="mt-3 flex flex-col divide-y divide-brand-roots/[.08]">
						<li v-for="item in part.items" :key="item.kra" class="flex items-center gap-3 py-2.5">
							<span class="min-w-0 grow text-[14px] text-brand-ink">{{ item.kra }}</span>
							<span class="shrink-0 text-[14px] font-semibold text-brand-ink" dir="ltr">{{ points(item.score) }} / {{ points(item.weight) }}</span>
						</li>
					</ul>
					<div v-if="hasText(part.notes)" class="mt-2 rounded-2xl bg-brand-sand/60 px-3 py-2.5">
						<div class="ms-caption">{{ __("Notes") }}</div>
						<div class="prose prose-sm max-w-none text-brand-ink" v-html="part.notes" />
					</div>
				</section>

				<!-- Acknowledging -->
				<section class="ms-card mx-4 mb-8 mt-3 p-4" :aria-label="__('Acknowledgement')">
					<template v-if="data.acknowledged_on">
						<div class="flex items-center gap-2 text-[14.5px] font-semibold text-state-success-text">
							<AppIcon name="check" :size="18" />
							{{ __("You acknowledged it on {0}", [dayjs(data.acknowledged_on).format("D MMM YYYY")]) }}
						</div>
						<p v-if="data.employee_comment" class="mt-2 text-[14px] leading-6 text-brand-ink/80">{{ data.employee_comment }}</p>
					</template>
					<template v-else>
						<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Have you read your evaluation?") }}</h2>
						<p class="ms-caption mt-1">{{ __("Acknowledge it, with a comment for HR if you have one. Only HR reads your comment.") }}</p>
						<textarea
							v-model="comment"
							rows="3"
							maxlength="2000"
							class="mt-3 w-full rounded-[14px] border-[1.5px] border-brand-roots/[.12] bg-brand-sand/[.45] p-3 text-[15px] text-brand-ink"
							:placeholder="__('Your comment (optional)')"
						/>
						<button type="button" class="ms-primary-button mt-3 w-full" :disabled="acknowledging" @click="acknowledge">
							<AppIcon name="check" :size="20" />
							{{ __("I've read my evaluation") }}
						</button>
					</template>
				</section>
			</template>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { IonPage, IonContent } from "@ionic/vue"
import { call, createResource, toast } from "frappe-ui"

import SubHeader from "@/components/ui/SubHeader.vue"
import Ring from "@/components/ui/Ring.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { formatCurrency } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({ id: { type: String, required: true } })

const evaluation = createResource({
	url: "ms_hrms.my_evaluations.get_my_evaluation",
	params: { name: props.id },
	auto: true,
})
const data = computed(() => evaluation.data)

const score = (value) => `${Math.round(value || 0)}%`
const points = (value) => `${Math.round((value || 0) * 10) / 10}`
const share = (value, of) => (of ? Math.min(100, Math.round((value / of) * 100)) : 0)
const hasText = (html) => Boolean((html || "").replace(/<[^>]*>/g, "").trim())
const period = computed(() => `${dayjs(data.value.from_date).format("D MMM")} – ${dayjs(data.value.to_date).format("D MMM YYYY")}`)
const change = computed(() =>
	data.value?.previous_score === null || data.value?.previous_score === undefined
		? null
		: Math.round(data.value.final_score - data.value.previous_score)
)

const comment = ref("")
const acknowledging = ref(false)

async function acknowledge() {
	acknowledging.value = true
	try {
		await call("ms_hrms.my_evaluations.acknowledge", { name: props.id, comment: comment.value })
		await evaluation.reload()
		toast({ title: __("Success"), text: __("Thank you. HR knows you read it."), icon: "check-circle", position: "bottom-center", iconClasses: "text-green-500" })
	} catch (error) {
		toast({ title: __("Error"), text: error.messages?.[0] || __("Something went wrong"), icon: "alert-circle", position: "bottom-center", iconClasses: "text-red-500" })
	} finally {
		acknowledging.value = false
	}
}
</script>
