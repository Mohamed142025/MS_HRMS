<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full sm:w-96">
				<!-- ms-app-* classes are the hooks for themes (ms_hrms_pwa_include_css). -->
				<div class="ms-app-header flex flex-col bg-white shadow-sm p-4">
					<div class="flex flex-row justify-between items-center">
						<div class="flex flex-row items-center gap-2 min-w-0">
							<!-- The home screen shows the site's logo on the dark bar a theme gives it; other
							     screens, and sites without such a theme, show the title. -->
							<img
								v-if="!props.pageTitle && brand.logo && brand.dark_header"
								:src="brand.logo"
								:alt="brand.app_title"
								class="ms-app-logo h-8 w-auto max-w-[60vw] object-contain"
							/>
							<h2 v-else class="ms-app-title text-xl font-bold text-gray-900 truncate">
								{{ props.pageTitle || brand.app_title }}
							</h2>
						</div>
						<div class="flex flex-row items-center gap-3 ms-auto">
							<router-link
								:to="{ name: 'Notifications' }"
								v-slot="{ navigate }"
								class="flex flex-col items-center"
							>
								<span class="relative inline-block" @click="navigate">
									<FeatherIcon name="bell" class="h-6 w-6" />
									<span
										v-if="unreadNotificationsCount.data"
										class="absolute top-0 end-0.5 inline-block w-2 h-2 bg-red-600 rounded-full border border-white"
									>
									</span>
								</span>
							</router-link>
							<router-link
								:to="{ name: 'Profile' }"
								class="flex flex-col items-center"
							>
								<Avatar
									:image="user.data.user_image"
									:label="user.data.first_name"
									size="xl"
								/>
							</router-link>
						</div>
					</div>
				</div>
			</div>
		</ion-header>

		<ion-content class="ion-no-padding">
			<div class="flex flex-col h-screen w-screen sm:w-96">
				<slot name="body"></slot>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonHeader, IonContent, IonPage } from "@ionic/vue"
import { FeatherIcon, Avatar } from "frappe-ui"

import { unreadNotificationsCount } from "@/data/notifications"
import { brand } from "@/data/brand"

import { inject } from "vue"

const user = inject("$user")

const props = defineProps({
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
})
</script>
