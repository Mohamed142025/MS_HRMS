<template>
	<!-- The finance tab's header: salary and expenses are two screens under one tab. -->
	<PageHeader :title="__('Finance')" :subtitle="__('Your salary and expenses')">
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
	</PageHeader>
	<Segmented
		class="mx-4 mt-4"
		:model-value="current"
		:options="[
			{ value: 'salary', label: __('Salary'), to: { name: 'SalarySlipsDashboard' } },
			{ value: 'expenses', label: __('Expenses & advances'), to: { name: 'ExpenseClaimsDashboard' } },
		]"
	/>
</template>

<script setup>
import PageHeader from "@/components/ui/PageHeader.vue"
import Segmented from "@/components/ui/Segmented.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { privacy } from "@/data/ui"

defineProps({ current: { type: String, required: true } })
</script>
