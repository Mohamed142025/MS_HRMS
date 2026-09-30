<template>
	<!-- A segmented control: buttons for a value, or links between sibling screens. -->
	<div class="ms-segmented" role="tablist" :style="{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }">
		<component
			:is="option.to ? 'router-link' : 'button'"
			v-for="option in options"
			:key="option.value"
			:to="option.to"
			:replace="Boolean(option.to)"
			type="button"
			role="tab"
			:aria-selected="option.value === modelValue"
			class="ms-segment"
			:class="option.value === modelValue && 'is-active'"
			@click="!option.to && $emit('update:modelValue', option.value)"
		>
			<span class="truncate">{{ option.label }}</span>
			<span
				v-if="option.badge"
				class="inline-flex h-[22px] min-w-[22px] items-center justify-center rounded-full bg-state-warning px-1.5 text-xs font-bold text-white"
			>
				{{ option.badge }}
			</span>
		</component>
	</div>
</template>

<script setup>
defineProps({
	options: { type: Array, required: true },
	modelValue: { type: String, default: "" },
})
defineEmits(["update:modelValue"])
</script>
