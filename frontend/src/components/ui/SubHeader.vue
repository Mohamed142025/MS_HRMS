<template>
	<!-- The header of a screen opened from another one: back, the title, actions. -->
	<header class="flex items-center gap-3 px-4 pt-[max(16px,env(safe-area-inset-top))]">
		<button type="button" class="ms-icon-button" :aria-label="__('Back')" @click="goBack">
			<AppIcon name="back" />
		</button>
		<div class="min-w-0 grow">
			<h1 class="truncate text-[22px] font-bold leading-snug text-brand-ink">{{ title }}</h1>
			<div v-if="subtitle" class="ms-caption truncate">{{ subtitle }}</div>
		</div>
		<slot name="actions" />
	</header>
</template>

<script setup>
import { useRouter } from "vue-router"
import AppIcon from "@/components/ui/AppIcon.vue"

const props = defineProps({
	title: { type: String, required: true },
	subtitle: { type: String, default: "" },
	// Where "back" goes when the screen was opened directly (no history to go back to).
	fallback: { type: [String, Object], default: "/home" },
})

const router = useRouter()

function goBack() {
	if (window.history.state?.back) router.back()
	else router.replace(props.fallback)
}
</script>
