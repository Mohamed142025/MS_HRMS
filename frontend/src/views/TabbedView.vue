<template>
	<ion-page>
		<ion-tabs>
			<ion-router-outlet></ion-router-outlet>
			<BottomTabs />
		</ion-tabs>
		<NewRequestSheet />
	</ion-page>
</template>

<script setup>
import { defineAsyncComponent } from "vue"
import { IonTabs, IonPage, IonRouterOutlet } from "@ionic/vue"
import BottomTabs from "@/components/BottomTabs.vue"

// Loaded with the tabs' first screen: its data modules read the signed-in employee, known
// only once the router has let the user in.
const NewRequestSheet = defineAsyncComponent(() => import("@/components/NewRequestSheet.vue"))
</script>
