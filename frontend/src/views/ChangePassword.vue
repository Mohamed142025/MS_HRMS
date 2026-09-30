<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="ms-form flex h-full w-full flex-col bg-brand-sand">
				<div class="flex h-full w-full flex-col">
					<SubHeader :title="__('Change Password')" fallback="/profile" />

					<div class="grow overflow-y-auto pb-6">
						<form class="ms-card mx-4 mt-4 flex flex-col space-y-4 p-4" @submit.prevent="submitPasswordChange">
							<Input
								:label="__('Current Password') + ' *'"
								type="password"
								v-model="currentPassword"
								autocomplete="current-password"
								required
							/>
							<Input
								:label="__('New Password') + ' *'"
								type="password"
								v-model="newPassword"
								autocomplete="new-password"
								required
							/>
							<Input
								:label="__('Confirm New Password') + ' *'"
								type="password"
								v-model="confirmPassword"
								autocomplete="new-password"
								required
							/>
						</form>
					</div>

					<div
						class="sticky bottom-0 z-40 w-full border-t border-brand-roots/[.08] bg-white px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3.5"
					>
						<ErrorMessage class="mb-2" :message="changePasswordError" />
						<Button
							class="w-full !h-14 !rounded-[18px] !text-base !font-bold disabled:bg-gray-700 disabled:text-white"
							:loading="updatePasswordResource.loading"
							variant="solid"
							@click="submitPasswordChange"
						>
							{{ __("Update Password") }}
						</Button>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import SubHeader from "@/components/ui/SubHeader.vue"
import { useRouter } from "vue-router"
import { FeatherIcon, toast, createResource, Input, ErrorMessage, Button } from "frappe-ui"

import { inject, ref } from "vue"

const __ = inject("$translate")
const router = useRouter()

const changePasswordError = ref("")
const currentPassword = ref("")
const newPassword = ref("")
const confirmPassword = ref("")

const updatePasswordResource = createResource({
	url: "frappe.core.doctype.user.user.update_password",
	method: "POST",
	onSuccess() {
		toast({
			title: __("Success"),
			text: __("Your password has been updated."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		resetForm()
		router.back()
	},
	onError(error) {
		changePasswordError.value = error.messages?.[0] || __("Failed to update password")
	},
})

function resetForm() {
	changePasswordError.value = ""
	currentPassword.value = ""
	newPassword.value = ""
	confirmPassword.value = ""
}

function submitPasswordChange() {
	if (!currentPassword.value || !newPassword.value || !confirmPassword.value) {
		changePasswordError.value = __("Please fill all fields")
		return
	}

	if (newPassword.value !== confirmPassword.value) {
		changePasswordError.value = __("New passwords do not match")
		return
	}

	changePasswordError.value = ""
	updatePasswordResource.submit({
		old_password: currentPassword.value,
		new_password: newPassword.value,
	})
}
</script>
