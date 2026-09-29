<template>
	<ion-page>
		<ion-content class="ion-padding">
			<div class="flex flex-col h-screen w-screen">
				<div class="w-full sm:w-96">
					<header
						class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b sticky top-0 z-10"
					>
						<div class="flex flex-row items-center">
							<Button
								variant="ghost"
								class="!ps-0 hover:bg-white"
								@click="router.back()"
							>
								<FeatherIcon name="chevron-left" class="h-5 w-5" />
							</Button>
							<h2 class="text-xl font-semibold text-gray-900">{{ __("Settings") }} </h2>
						</div>
					</header>

					<div class="flex flex-col gap-5 my-4 w-full p-4">
						<div class="flex flex-col bg-white rounded">
							<div
								class="flex flex-row cursor-pointer flex-start p-4 items-center justify-between border-b"
							>
								<router-link
									:to="{ name: 'ChangePassword' }"
									class="flex flex-row items-center justify-between w-full"
								>
									<div class="flex flex-row items-center gap-3 grow">
										<FeatherIcon
											name="lock"
											class="h-5 w-5 text-gray-500"
										/>
										<div class="text-base font-normal text-gray-800">
											{{ __("Change Password") }}
										</div>
									</div>
									<FeatherIcon
										name="chevron-right"
										class="h-5 w-5 text-gray-500"
									/>
								</router-link>
							</div>
						</div>

						<!-- The user's own language: the app reloads in it, direction included. -->
						<div v-if="languages.length > 1" class="ms-settings-language flex flex-col bg-white rounded">
							<label class="flex flex-row items-center justify-between gap-3 p-4">
								<span class="flex flex-row items-center gap-3 grow">
									<FeatherIcon name="globe" class="h-5 w-5 text-gray-500" />
									<span class="text-base font-normal text-gray-800">{{ __("Language") }}</span>
								</span>
								<select
									class="form-select rounded border-gray-300 bg-gray-100 py-1.5 text-base text-gray-800"
									:value="currentLanguage"
									:disabled="changingLanguage"
									@change="changeLanguage($event.target.value)"
								>
									<option v-for="language in languages" :key="language.value" :value="language.value">
										{{ language.label }}
									</option>
								</select>
							</label>
						</div>

						<div class="flex flex-col bg-white rounded">
							<Switch
								size="md"
								:label="__('Enable Push Notifications')"
								:class="description ? 'p-2' : ''"
								:model-value="pushNotificationState"
								:disabled="disablePushSetting"
								:description="description"
								@update:model-value="togglePushNotifications"
							/>
						</div>

						<div
							v-if="isLoading"
							class="flex -mt-2 items-center justify-center gap-2"
						>
							<LoadingIndicator class="w-3 h-3 text-gray-800" />
							<span class="text-gray-900 text-sm">
								{{ pushNotificationState ? __("Disabling Push Notifications...") : __("Enabling Push Notifications...") }}
							</span>
						</div>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { useRouter } from "vue-router"
import { FeatherIcon, Switch, toast, LoadingIndicator, Button, call } from "frappe-ui"

import { computed, inject, ref } from "vue"

import { arePushNotificationsEnabled } from "@/data/notifications"
import { languages } from "@/data/brand"

const __ = inject("$translate")
const router = useRouter()

const pushNotificationState = ref(
	window.frappePushNotification?.isNotificationEnabled()
)
const isLoading = ref(false)

const currentLanguage = window.frappe?.boot?.lang
const changingLanguage = ref(false)

function changeLanguage(language) {
	if (language === currentLanguage) return
	changingLanguage.value = true
	call("ms_hrms.pwa.set_language", { language })
		.then(() => window.location.reload())
		.catch((error) => {
			changingLanguage.value = false
			toast({
				title: __("Error"),
				text: error.messages?.[0] || error.message,
				icon: "alert-circle",
				position: "bottom-center",
				iconClasses: "text-red-500",
			})
		})
}

const disablePushSetting = computed(() => {
	return (
		!(
			window.frappe?.boot.push_relay_server_url &&
			arePushNotificationsEnabled.data
		) || isLoading.value
	)
})

const description = computed(() => {
	return !(
		window.frappe?.boot.push_relay_server_url &&
		arePushNotificationsEnabled.data
	)
		? __("Push notifications have been disabled on your site")
		: ""
})

const togglePushNotifications = (newValue) => {
	if (newValue) {
		enablePushNotifications()
	} else {
		isLoading.value = true
		window.frappePushNotification
			.disableNotification()
			.then(() => {
				pushNotificationState.value = false
				toast({
					title: __("Success"),
					text: __("Push notifications disabled"),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			})
			.catch((error) => {
				toast({
					title: __("Error"),
					text: __(error.message),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			})
			.finally(() => {
				isLoading.value = false
			})
	}
}
const enablePushNotifications = () => {
	isLoading.value = true

	window.frappePushNotification
		.enableNotification()
		.then((data) => {
			if (data.permission_granted) {
				pushNotificationState.value = true
			} else {
				toast({
					title: __("Error"),
					text: __("Push Notification permission denied"),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
				pushNotificationState.value = false
			}
		})
		.catch((error) => {
			toast({
				title: __("Error"),
				text: __(error.message),
				icon: "alert-circle",
				position: "bottom-center",
				iconClasses: "text-red-500",
			})
			pushNotificationState.value = false
		})
		.finally(() => {
			isLoading.value = false
		})
}

</script>