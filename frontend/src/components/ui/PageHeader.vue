<template>
	<!-- The header of a main (tab) screen: a large title with a line above it. -->
	<header class="flex items-end justify-between gap-3 px-4 pt-[max(20px,env(safe-area-inset-top))]">
		<div class="min-w-0">
			<div v-if="subtitle" class="ms-caption truncate">{{ subtitle }}</div>
			<h1 class="text-[28px] font-bold leading-tight text-brand-ink">{{ title }}</h1>
		</div>
		<div class="flex shrink-0 items-center gap-2">
			<slot name="actions" />
		</div>
	</header>
</template>

<script setup>
defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
})
</script>
