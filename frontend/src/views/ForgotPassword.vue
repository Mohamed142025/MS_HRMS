<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="ms-form flex h-full w-full flex-col bg-brand-sand">
				<div class="flex h-full w-full flex-col">
					<SubHeader :title="__('Reset Password')" fallback="/login" />

					<div class="grow overflow-y-auto pb-6">
						<form class="ms-card mx-4 mt-4 flex flex-col space-y-4 p-4" @submit.prevent="sendPasswordReset">
							<p class="text-sm leading-6 text-brand-muted">
								{{ __("Enter your email address and we'll send you a link to reset your password.") }}
							</p>
							<Input
								:label="__('Email') + ' *'"
								type="email"
								placeholder="johndoe@mail.com"
								v-model="email"
								autocomplete="username"
								required
							/>
						</form>
					</div>

					<div
						class="sticky bottom-0 z-40 w-full border-t border-brand-roots/[.08] bg-white px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3.5"
					>
						<ErrorMessage class="mb-2" :message="errorMessage" />
						<Button
							class="w-full !h-14 !rounded-[18px] !text-base !font-bold disabled:bg-gray-700 disabled:text-white"
							:loading="forgotPasswordResource.loading"
							variant="solid"
							@click="sendPasswordReset"
						>
							{{ __("Send Reset Link") }}
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
import { useRoute, useRouter } from "vue-router"
import { FeatherIcon, toast, createResource, Input, ErrorMessage, Button } from "frappe-ui"

import { inject, ref } from "vue"

const __ = inject("$translate")
const route = useRoute()
const router = useRouter()

const email = ref(Array.isArray(route.query.email) ? route.query.email[0] : route.query.email || "")
const errorMessage = ref("")

const forgotPasswordResource = createResource({
	url: "frappe.core.doctype.user.user.reset_password",
	method: "POST",
	onSuccess() {
		toast({
			title: __("Success"),
			text: __("Password reset link has been sent to your email."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		errorMessage.value = ""
		router.replace({ name: "Login" })
	},
	onError(error) {
		errorMessage.value = error.messages?.[0] || __("Failed to send reset link")
	},
})

function isValidEmail(value) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function goBack() {
	if (window.history.state?.back) {
		router.back()
		return
	}

	router.replace({ name: "Login" })
}

function sendPasswordReset() {
	const emailValue = (email.value || "").trim()

	if (!emailValue) {
		errorMessage.value = __("Please enter your email address")
		return
	}

	if (!isValidEmail(emailValue)) {
		errorMessage.value = __("Please enter a valid email address")
		return
	}

	errorMessage.value = ""
	forgotPasswordResource.submit({ user: emailValue })
}
</script>
