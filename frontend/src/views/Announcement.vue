<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('From HR')" fallback="/notifications" />

			<div v-if="announcement.error" class="ms-caption p-10 text-center">
				{{ announcement.error.messages?.[0] || __("This announcement was not sent to you.") }}
			</div>
			<div v-else-if="!data" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<article v-else class="ms-card mx-4 mb-8 mt-4 p-[18px]">
				<div class="flex items-center gap-3">
					<span class="ms-icon-tile h-[42px] w-[42px]" :class="TONES.roots">
						<AppIcon name="bell" :size="20" />
					</span>
					<div class="min-w-0">
						<h1 class="text-[18px] font-bold leading-7 text-brand-ink">{{ data.title }}</h1>
						<p class="ms-caption">
							{{ data.sent_on ? dayjs(data.sent_on).format("D MMM YYYY, h:mm A") : "" }}
							<template v-if="data.department"> · {{ data.department }}</template>
						</p>
					</div>
				</div>
				<!-- Sanitised on the server; written in the desk's text editor. -->
				<div class="ms-rich-text prose prose-sm mt-4 max-w-none text-brand-ink" v-html="data.message" />
			</article>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"

import SubHeader from "@/components/ui/SubHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { TONES } from "@/utils/requestTypes"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({ id: { type: String, required: true } })

const announcement = createResource({
	url: "ms_hrms.app_notifications.get_announcement",
	params: { name: props.id },
	auto: true,
})
const data = computed(() => announcement.data)
</script>
