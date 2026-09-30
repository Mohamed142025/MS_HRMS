<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<SubHeader :title="__('Settings')" fallback="/profile" />

			<div class="ms-card mx-4 mt-4 px-3.5">
				<router-link :to="{ name: 'ChangePassword' }" class="ms-list-row">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon name="lock" :size="20" /></span>
					<span class="grow text-[15px] font-medium text-brand-ink">{{ __("Change Password") }}</span>
					<AppIcon name="forward" :size="18" class="text-brand-muted" />
				</router-link>

				<!-- The user's own language: the app reloads in it, direction included. -->
				<div v-if="languages.length > 1" class="ms-list-row ms-settings-language">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon name="globe" :size="20" /></span>
					<span class="grow text-[15px] font-medium text-brand-ink">{{ __("Language") }}</span>
					<span role="radiogroup" :aria-label="__('Language')" class="flex gap-0.5 rounded-xl bg-brand-sand p-[3px]">
						<button
							v-for="option in languages"
							:key="option.value"
							type="button"
							role="radio"
							:aria-checked="option.value === language.current"
							class="h-[34px] rounded-[10px] px-3 text-[13px] font-semibold"
							:class="option.value === language.current ? 'bg-brand-roots text-brand-sand' : 'text-brand-ink/80'"
							:disabled="language.changing.value"
							@click="language.change(option.value)"
						>
							{{ option.label }}
						</button>
					</span>
				</div>

				<div class="ms-list-row">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon name="bell" :size="20" /></span>
					<span class="min-w-0 grow">
						<span class="block text-[15px] font-medium text-brand-ink">{{ __("Enable Push Notifications") }}</span>
						<span v-if="push.description.value" class="block text-xs text-brand-muted">{{ push.description.value }}</span>
						<span v-if="push.loading.value" class="block text-xs text-brand-muted">
							{{ push.enabled.value ? __("Disabling Push Notifications...") : __("Enabling Push Notifications...") }}
						</span>
					</span>
					<button
						type="button"
						role="switch"
						:aria-checked="Boolean(push.enabled.value)"
						:aria-label="__('Enable Push Notifications')"
						class="relative h-8 w-[52px] shrink-0 rounded-full transition disabled:opacity-50"
						:class="push.enabled.value ? 'bg-brand-emerald' : 'bg-brand-roots/[.18]'"
						:disabled="push.disabled.value"
						@click="push.toggle(!push.enabled.value)"
					>
						<span class="absolute top-[3px] h-[26px] w-[26px] rounded-full bg-white shadow transition-all" :class="push.enabled.value ? 'end-[3px]' : 'start-[3px]'" />
					</button>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"

import SubHeader from "@/components/ui/SubHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { languages } from "@/data/brand"
import { usePushNotifications } from "@/composables/pushNotifications"
import { useLanguage } from "@/composables/language"

const push = usePushNotifications()
const language = useLanguage()
</script>
