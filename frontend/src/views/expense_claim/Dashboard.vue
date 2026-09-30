<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<FinanceHeader current="expenses" />

			<section class="ms-card mx-4 mt-4 p-[18px]" :aria-label="__('Your claims')">
				<h2 class="text-[13.5px] font-semibold text-brand-muted">{{ __("Your claims in {0}", [dayjs().year()]) }}</h2>
				<div class="mt-1 flex items-baseline gap-1.5">
					<span class="text-[32px] font-bold leading-tight text-brand-ink">{{ amount(data?.total) }}</span>
					<span class="text-[15px] font-semibold text-brand-muted">{{ __(data?.currency) }}</span>
				</div>

				<div class="mt-3 grid grid-cols-3 gap-2">
					<div v-for="stage in stages" :key="stage.label" class="rounded-2xl px-2.5 py-2" :class="stage.tone">
						<div class="text-[15px] font-bold">{{ amount(stage.value) }}</div>
						<div class="text-[11.5px]">{{ stage.label }}</div>
					</div>
				</div>

				<template v-if="byType.length">
					<h3 class="mb-3 mt-5 text-[14px] font-bold text-brand-ink">{{ __("By expense type") }}</h3>
					<BarList :rows="byType" />
				</template>
			</section>

			<section class="ms-dark-card mx-4 mt-3 p-[18px]" :aria-label="__('Employee Advances')">
				<div class="flex items-center justify-between gap-2">
					<h2 class="text-[15.5px] font-bold">{{ __("Employee Advances") }}</h2>
					<router-link :to="{ name: 'EmployeeAdvanceListView' }" class="inline-flex min-h-[44px] items-center text-[13.5px] font-semibold text-brand-mint">
						{{ __("View all") }}
					</router-link>
				</div>
				<template v-if="advances.length">
					<div class="flex items-baseline gap-1.5">
						<span class="text-[26px] font-bold">{{ amount(advanceTotal) }}</span>
						<span class="text-sm text-brand-sand/70">{{ __("outstanding") }}</span>
					</div>
					<div class="mt-2 flex flex-col">
						<router-link
							v-for="advance in advances"
							:key="advance.name"
							:to="{ name: 'EmployeeAdvanceDetailView', params: { id: advance.name } }"
							class="flex items-center justify-between gap-3 border-b border-brand-sand/[.12] py-2.5 last:border-b-0"
						>
							<span class="min-w-0">
								<span class="block truncate text-[14.5px] font-semibold">{{ advance.purpose }}</span>
								<span class="block text-xs text-brand-sand/70">{{ dayjs(advance.posting_date).format("D MMM YYYY") }} · {{ __(advance.status, null, "Employee Advance") }}</span>
							</span>
							<span class="shrink-0 text-[15px] font-bold">{{ amount(advance.balance_amount) }}</span>
						</router-link>
					</div>
				</template>
				<p v-else class="mt-1 text-[13.5px] text-brand-sand/70">{{ __("You have no advances") }}</p>
				<router-link
					:to="{ name: 'EmployeeAdvanceFormView' }"
					class="mt-3 flex h-12 items-center justify-center gap-2 rounded-[14px] bg-brand-mint text-[15px] font-bold text-brand-roots"
				>
					<AppIcon name="plus" :size="18" :stroke-width="2.2" />
					{{ __("Request an Advance") }}
				</router-link>
			</section>

			<section class="mx-4 mt-5" :aria-label="__('Recent Expenses')">
				<div class="mb-1 flex items-center justify-between">
					<h2 class="ms-group-title">{{ __("Recent Expenses") }}</h2>
					<router-link :to="{ name: 'ExpenseClaimListView' }" class="ms-link">{{ __("View all") }}</router-link>
				</div>
				<div v-if="recent.length" class="ms-card px-3.5">
					<router-link
						v-for="claim in recent"
						:key="claim.name"
						:to="{ name: 'ExpenseClaimDetailView', params: { id: claim.name } }"
						class="ms-list-row"
					>
						<span class="ms-icon-tile bg-brand-roots/[.08] text-brand-roots"><AppIcon name="receipt" :size="20" /></span>
						<span class="min-w-0 grow">
							<span class="block truncate text-[15px] font-semibold text-brand-ink">
								{{ claim.expense_types.map((type) => __(type)).join("، ") || __("Expense Claim") }}
							</span>
							<span class="block truncate text-[12.5px] text-brand-muted">{{ dayjs(claim.posting_date).format("D MMMM") }}</span>
						</span>
						<span class="shrink-0 text-end">
							<span class="block text-[15px] font-bold text-brand-ink">{{ amount(claim.total_claimed_amount) }}</span>
							<StatusChip :status="requestStatus({ ...claim, doctype: 'Expense Claim' })" class="mt-0.5" />
						</span>
					</router-link>
				</div>
				<div v-else class="ms-caption rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-6 text-center">
					{{ __("You have no expense claims this year") }}
				</div>
			</section>

			<div class="mx-4 mb-8 mt-4">
				<router-link :to="{ name: 'ExpenseClaimFormView' }" class="ms-primary-button">
					<AppIcon name="plus" :size="20" :stroke-width="2.2" />
					{{ __("Claim an Expense") }}
				</router-link>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"

import FinanceHeader from "@/components/FinanceHeader.vue"
import BarList from "@/components/ui/BarList.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import StatusChip from "@/components/ui/StatusChip.vue"

import { expenses } from "@/data/pwa"
import { advanceBalance } from "@/data/advances"
import { privacy } from "@/data/ui"
import { formatNumber } from "@/utils/formatters"
import { requestStatus } from "@/utils/requestTypes"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

onMounted(() => {
	expenses.reload()
	advanceBalance.reload()
})

async function refresh(event) {
	await Promise.allSettled([expenses.reload(), advanceBalance.reload()])
	event.target.complete()
}

const data = computed(() => expenses.data)
const amount = (value) => (privacy.hidden ? "••••" : formatNumber(value || 0, 0))

const stages = computed(() => [
	{ label: __("Paid"), value: data.value?.stages?.paid, tone: "bg-brand-sand text-brand-ink" },
	{ label: __("Approved"), value: data.value?.stages?.approved, tone: "bg-brand-sand text-brand-ink" },
	{ label: __("Pending"), value: data.value?.stages?.pending, tone: "bg-state-warning/[.12] text-state-warning-text" },
])

const byType = computed(() =>
	(data.value?.by_type || []).map((row) => ({ label: __(row.expense_type), value: row.amount, display: amount(row.amount) }))
)

const recent = computed(() => data.value?.recent || [])
const advances = computed(() => (advanceBalance.data || []).filter((advance) => advance.balance_amount > 0))
const advanceTotal = computed(() => advances.value.reduce((sum, advance) => sum + advance.balance_amount, 0))
</script>
