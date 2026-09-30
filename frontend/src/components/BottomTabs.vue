<template>
	<!-- The main tabs on Roots green, with the "new request" button in the middle.
	     ms-tabbar and ms-tab are also hooks for themes (ms_hrms_pwa_include_css). -->
	<ion-tab-bar slot="bottom" class="ms-tabbar">
		<ion-tab-button
			v-for="item in tabs.slice(0, 2)"
			:key="item.tab"
			:tab="item.tab"
			:href="item.route"
			class="ms-tab"
			:class="isActive(item) && 'is-active'"
		>
			<span class="ms-tab-inner">
				<AppIcon :name="item.icon" />
				<span>{{ item.title }}</span>
			</span>
		</ion-tab-button>

		<button type="button" class="ms-tab-fab" :aria-label="__('New request')" @click="newRequestSheet.open = true">
			<AppIcon name="plus" :size="26" :stroke-width="2.4" />
		</button>

		<ion-tab-button
			v-for="item in tabs.slice(2)"
			:key="item.tab"
			:tab="item.tab"
			:href="item.route"
			class="ms-tab"
			:class="isActive(item) && 'is-active'"
		>
			<span class="ms-tab-inner">
				<AppIcon :name="item.icon" />
				<span>{{ item.title }}</span>
			</span>
		</ion-tab-button>
	</ion-tab-bar>
</template>

<script setup>
import { inject } from "vue"
import { useRoute } from "vue-router"
import { IonTabBar, IonTabButton } from "@ionic/vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import { newRequestSheet } from "@/data/ui"

const __ = inject("$translate")
const route = useRoute()

// Each tab also stays lit on the screens reached from it.
const tabs = [
	{ tab: "home", icon: "home", title: __("Home"), route: "/home", paths: ["/home"] },
	{ tab: "attendance", icon: "clock", title: __("Attendance"), route: "/dashboard/attendance", paths: ["/dashboard/attendance"] },
	{
		tab: "requests",
		icon: "clipboard",
		title: __("Requests"),
		route: "/requests",
		paths: ["/requests", "/approvals", "/dashboard/leaves"],
	},
	{
		tab: "finance",
		icon: "wallet",
		title: __("Finance"),
		route: "/dashboard/salary-slips",
		paths: ["/dashboard/salary-slips", "/dashboard/expense-claims"],
	},
]

const isActive = (item) => item.paths.some((path) => route.path.startsWith(path))
</script>
