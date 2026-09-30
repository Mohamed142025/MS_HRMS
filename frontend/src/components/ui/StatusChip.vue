<template>
	<span class="ms-chip" :class="statusTone(status)">{{ label || __(status) }}</span>
</template>

<script setup>
import { statusTone } from "@/utils/requestTypes"

defineProps({
	status: { type: String, default: "" },
	label: { type: String, default: "" },
})
</script>
