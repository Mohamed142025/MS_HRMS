<template>
	<ion-modal
		:is-open="newRequestSheet.open"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
		class="ms-sheet"
		@didDismiss="newRequestSheet.open = false"
	>
		<div class="bg-white px-4 pb-[max(24px,env(safe-area-inset-bottom))] pt-5">
			<div class="flex items-center justify-between">
				<div>
					<h2 class="text-[21px] font-bold text-brand-ink">{{ __("New request") }}</h2>
					<p class="ms-caption">{{ __("Choose the type of request") }}</p>
				</div>
				<button type="button" class="ms-icon-tile bg-brand-sand text-brand-roots" :aria-label="__('Close')" @click="newRequestSheet.open = false">
					<AppIcon name="x" :size="20" />
				</button>
			</div>

			<div class="mt-4 grid grid-cols-2 gap-2.5">
				<button
					v-for="item in tiles"
					:key="item.doctype"
					type="button"
					class="flex flex-col gap-2.5 rounded-[20px] border border-brand-roots/[.08] bg-brand-sand/50 p-3.5 text-start transition active:scale-[.98]"
					@click="open(item)"
				>
					<span class="ms-icon-tile h-[42px] w-[42px]" :class="TONES[REQUEST_TYPES[item.doctype].tone]">
						<AppIcon :name="REQUEST_TYPES[item.doctype].icon" />
					</span>
					<span>
						<span class="block text-[15px] font-bold text-brand-ink">{{ item.title }}</span>
						<span class="block text-[12.5px] text-brand-muted">{{ item.hint }}</span>
					</span>
				</button>
			</div>

			<button
				type="button"
				class="mt-2.5 flex w-full items-center gap-3 rounded-[20px] border border-brand-roots/[.08] bg-brand-sand/50 px-3.5 py-3 text-start transition active:scale-[.98]"
				@click="open(attendance)"
			>
				<span class="ms-icon-tile h-[42px] w-[42px]" :class="TONES[REQUEST_TYPES['Attendance Request'].tone]">
					<AppIcon :name="REQUEST_TYPES['Attendance Request'].icon" />
				</span>
				<span class="grow">
					<span class="block text-[15px] font-bold text-brand-ink">{{ attendance.title }}</span>
					<span class="block text-[12.5px] text-brand-muted">{{ attendance.hint }}</span>
				</span>
				<AppIcon name="forward" :size="18" class="text-brand-muted" />
			</button>
		</div>
	</ion-modal>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRouter } from "vue-router"
import { IonModal } from "@ionic/vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import { REQUEST_TYPES, TONES } from "@/utils/requestTypes"
import { newRequestSheet } from "@/data/ui"
import { leaveBalance } from "@/data/leaves"
import { formatNumber } from "@/utils/formatters"

const __ = inject("$translate")
const router = useRouter()

const leaveHint = computed(() => {
	const balances = Object.values(leaveBalance.data || {})
	if (!balances.length) return __("Days off from work")
	const main = balances.reduce((a, b) => (b.allocated_leaves > a.allocated_leaves ? b : a))
	return __("Your balance: {0} days", [formatNumber(main.balance_leaves)])
})

const tiles = computed(() => [
	{ doctype: "Leave Application", title: __("Request Leave"), hint: leaveHint.value },
	{ doctype: "Permission Request", title: __("Permission Request"), hint: __("A few hours of the workday") },
	{ doctype: "Overtime Request", title: __("Overtime Request"), hint: __("Record your extra hours") },
	{ doctype: "Expense Claim", title: __("Claim an Expense"), hint: __("Attach a photo of the receipt") },
	{ doctype: "Employee Advance", title: __("Request an Advance"), hint: __("Recovered from your salary") },
	{ doctype: "Shift Request", title: __("Request a Shift"), hint: __("Change your working hours") },
])

const attendance = {
	doctype: "Attendance Request",
	title: __("Request Attendance"),
	hint: __("Forgot to check in or out?"),
}

function open(item) {
	newRequestSheet.open = false
	router.push({ name: REQUEST_TYPES[item.doctype].newRoute })
}
</script>
