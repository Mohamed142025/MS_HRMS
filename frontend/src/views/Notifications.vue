<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('Notifications')" fallback="/home">
				<template #actions>
					<button
						v-if="unreadNotificationsCount.data"
						type="button"
						class="min-h-[44px] shrink-0 px-1 text-[14px] font-semibold text-brand-emerald disabled:opacity-60"
						:disabled="markAllAsRead.loading"
						@click="markAllAsRead.submit()"
					>
						{{ __("Mark all as read") }}
					</button>
					<router-link v-else-if="allowPushNotifications" :to="{ name: 'Settings' }" class="ms-icon-button" :aria-label="__('Settings')">
						<AppIcon name="sliders" :size="20" />
					</router-link>
				</template>
			</SubHeader>

			<div class="hide-scrollbar mt-4 flex gap-2 overflow-x-auto px-4">
				<button
					v-for="option in filters"
					:key="option.value"
					type="button"
					class="ms-filter-chip"
					:class="filter === option.value && 'is-active'"
					:aria-pressed="filter === option.value"
					@click="filter = option.value"
				>
					{{ option.label }}
					<span
						v-if="option.value === 'unread' && unreadNotificationsCount.data"
						class="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-brand-mint px-1.5 text-xs font-bold text-brand-roots"
					>
						{{ unreadNotificationsCount.data }}
					</span>
				</button>
			</div>

			<template v-if="groups.length">
				<section v-for="group in groups" :key="group.title" :aria-label="group.title">
					<h2 class="ms-group-title mx-4 mb-2.5 mt-5">{{ group.title }}</h2>
					<div class="ms-card mx-4 px-3.5">
						<router-link
							v-for="item in group.items"
							:key="item.name"
							:to="getItemRoute(item)"
							class="ms-list-row items-start"
							@click="markAsRead(item.name)"
						>
							<span class="ms-icon-tile h-[42px] w-[42px]" :class="TONES[type(item).tone]">
								<AppIcon :name="type(item).icon" :size="20" />
							</span>
							<span class="min-w-0 grow">
								<span class="block text-[14.5px] leading-6 text-brand-ink" :class="!item.read && 'font-semibold'" v-html="item.message" />
								<span class="mt-0.5 block text-xs text-brand-muted">{{ dayjs(item.creation).fromNow() }}</span>
							</span>
							<span v-if="!item.read" class="mt-2 h-[9px] w-[9px] shrink-0 rounded-full bg-brand-emerald" :aria-label="__('Unread')" />
						</router-link>
					</div>
				</section>
				<div v-if="notifications.hasNextPage" class="mx-4 mt-4 flex justify-center">
					<button type="button" class="ms-secondary-button w-full" @click="loadMore">{{ __("Load more") }}</button>
				</div>
				<div class="h-8" />
			</template>
			<div
				v-else-if="notifications.data"
				class="ms-caption mx-4 mt-5 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center"
			>
				{{ filter === "unread" ? __("You have no unread notifications") : __("You have no notifications") }}
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonContent, IonPage } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { computed, inject, onMounted, ref } from "vue"

import SubHeader from "@/components/ui/SubHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"

import { unreadNotificationsCount, notifications, arePushNotificationsEnabled } from "@/data/notifications"
import { REQUEST_TYPES, TONES } from "@/utils/requestTypes"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const currentStart = ref(0)
const pageLength = 10

const allowPushNotifications = computed(
	() => window.frappe?.boot.push_relay_server_url && arePushNotificationsEnabled.data
)

const markAllAsRead = createResource({
	url: "hrms.api.mark_all_notifications_as_read",
	onSuccess() {
		notifications.reload()
	},
})

function markAsRead(name) {
	notifications.setValue.submit(
		{ name, read: 1 },
		{
			onSuccess: () => {
				unreadNotificationsCount.reload()
			},
		}
	)
}

function getItemRoute(item) {
	return {
		name: `${item.reference_document_type.replace(/\s+/g, "")}DetailView`,
		params: { id: item.reference_document_name },
	}
}

const type = (item) => REQUEST_TYPES[item.reference_document_type] || { icon: "bell", tone: "roots" }

const filter = ref("all")
const filters = [
	{ value: "all", label: __("All") },
	{ value: "unread", label: __("Unread") },
]

const groups = computed(() => {
	const items = (notifications.data || []).filter((item) => filter.value === "all" || !item.read)
	const today = []
	const week = []
	const older = []
	for (const item of items) {
		const when = dayjs(item.creation)
		if (when.isToday()) today.push(item)
		else if (dayjs().diff(when, "day") < 7) week.push(item)
		else older.push(item)
	}
	return [
		{ title: __("Today"), items: today },
		{ title: __("This week"), items: week },
		{ title: __("Earlier"), items: older },
	].filter((group) => group.items.length)
})

onMounted(() => {
	notifications.start = 0
	notifications.pageLength = 10
	notifications.fetch()
})

function loadMore() {
	currentStart.value += pageLength
	notifications.start = currentStart.value
	notifications.pageLength = pageLength
	notifications.list.fetch()
}
</script>
