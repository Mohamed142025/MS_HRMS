<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<PageHeader :title="__('Requests')" :subtitle="__('Leaves, permissions, overtime and expenses')" />

			<Segmented class="mx-4 mt-4" :options="tabs" model-value="mine" />

			<section v-if="balances.length" class="mt-5" :aria-label="__('Your balances')">
				<div class="mx-4 mb-1 flex items-center justify-between">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Your balances") }}</h2>
					<router-link :to="{ name: 'LeavesDashboard' }" class="ms-link">{{ __("All balances") }}</router-link>
				</div>
				<div class="hide-scrollbar flex gap-2.5 overflow-x-auto px-4 pb-1">
					<router-link
						v-for="balance in balances"
						:key="balance.type"
						:to="{ name: 'LeavesDashboard' }"
						class="flex w-[156px] shrink-0 items-center gap-2.5 rounded-[20px] bg-white p-3 shadow-sm"
					>
						<Ring :value="balance.share" :size="44" :stroke="14" />
						<span class="min-w-0">
							<span class="block text-lg font-bold text-brand-ink">{{ formatNumber(balance.balance) }}</span>
							<span class="block truncate text-xs text-brand-muted">{{ __(balance.type, null, "Leave Type") }}</span>
						</span>
					</router-link>
				</div>
			</section>

			<div class="hide-scrollbar mt-5 flex gap-2 overflow-x-auto px-4">
				<button
					v-for="chip in chips"
					:key="chip.value"
					type="button"
					class="ms-filter-chip"
					:class="filter === chip.value && 'is-active'"
					:aria-pressed="filter === chip.value"
					@click="filter = chip.value"
				>
					{{ chip.label }}
				</button>
			</div>

			<template v-if="filtered.length">
				<section v-for="group in groups" :key="group.key" :aria-label="group.title">
					<h2 class="ms-group-title mx-4 mb-2.5 mt-5">{{ group.title }}</h2>
					<div class="ms-card mx-4 px-3.5">
						<RequestRow v-for="doc in group.items" :key="`${doc.doctype}:${doc.name}`" :doc="doc" @open="selected = $event" />
					</div>
				</section>
			</template>
			<div v-else class="ms-caption mx-4 mt-5 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center">
				{{ __("You have no requests") }}
			</div>

			<div class="mx-4 mb-8 mt-4 flex flex-col gap-2.5">
				<router-link v-if="filter !== 'all'" :to="{ name: REQUEST_TYPES[filter].listRoute }" class="ms-secondary-button">
					{{ __("View all {0}", [chips.find((chip) => chip.value === filter)?.label]) }}
				</router-link>
				<button type="button" class="ms-primary-button" @click="newRequestSheet.open = true">
					<AppIcon name="plus" :size="20" :stroke-width="2.2" />
					{{ __("New request") }}
				</button>
			</div>

			<RequestSheet :request="selected" @close="selected = null" />
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"

import PageHeader from "@/components/ui/PageHeader.vue"
import Segmented from "@/components/ui/Segmented.vue"
import Ring from "@/components/ui/Ring.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import RequestRow from "@/components/RequestRow.vue"
import RequestSheet from "@/components/RequestSheet.vue"

import { myLeaves, leaveBalance, teamLeaves } from "@/data/leaves"
import { myClaims, teamClaims } from "@/data/claims"
import {
	myAttendanceRequests,
	myShiftRequests,
	myPermissionRequests,
	myOvertimeRequests,
	teamShiftRequests,
	teamAttendanceRequests,
	teamPermissionRequests,
	teamOvertimeRequests,
} from "@/data/attendance"
import { newRequestSheet } from "@/data/ui"
import { REQUEST_TYPES, isPending, typeLabel } from "@/utils/requestTypes"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const mine = [myLeaves, myClaims, myPermissionRequests, myOvertimeRequests, myShiftRequests, myAttendanceRequests]
const team = [teamLeaves, teamClaims, teamPermissionRequests, teamOvertimeRequests, teamShiftRequests, teamAttendanceRequests]

async function refresh(event) {
	await Promise.allSettled([...mine, ...team, leaveBalance].map((resource) => resource.reload()))
	event.target.complete()
}

const awaiting = computed(() => team.reduce((count, resource) => count + (resource.data?.length || 0), 0))
const tabs = computed(() => [
	{ value: "mine", label: __("My Requests"), to: { name: "Requests" } },
	{ value: "approvals", label: __("For approval"), to: { name: "Approvals" }, badge: awaiting.value || "" },
])

const balances = computed(() =>
	Object.entries(leaveBalance.data || {}).map(([type, allocation]) => ({
		type,
		balance: allocation.balance_leaves,
		share: Math.min((allocation.balance_leaves / (allocation.allocated_leaves || 1)) * 100, 100),
	}))
)

const requests = computed(() =>
	mine
		.flatMap((resource) => resource.data || [])
		.sort((a, b) => new Date(b.creation) - new Date(a.creation))
)

const filter = ref("all")
const chips = computed(() => [
	{ value: "all", label: __("All") },
	...Object.keys(REQUEST_TYPES)
		.filter((doctype) => doctype !== "Employee Advance")
		.map((doctype) => ({ value: doctype, label: typeLabel(doctype) })),
])

const filtered = computed(() =>
	filter.value === "all" ? requests.value : requests.value.filter((doc) => doc.doctype === filter.value)
)

const groups = computed(() => {
	const pending = filtered.value.filter(isPending)
	const rest = filtered.value.filter((doc) => !isPending(doc))
	const byMonth = new Map()
	for (const doc of rest) {
		const key = dayjs(doc.creation).format("YYYY-MM")
		if (!byMonth.has(key)) byMonth.set(key, [])
		byMonth.get(key).push(doc)
	}
	return [
		...(pending.length ? [{ key: "pending", title: __("Awaiting approval"), items: pending }] : []),
		...[...byMonth.entries()].map(([key, items]) => ({
			key,
			title: dayjs(`${key}-01`).format(dayjs(`${key}-01`).isSame(dayjs(), "year") ? "MMMM" : "MMMM YYYY"),
			items,
		})),
	]
})

const selected = ref(null)
</script>
