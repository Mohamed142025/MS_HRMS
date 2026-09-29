<template>
	<ion-page>
		<ListView
			doctype="Overtime Request"
			:pageTitle="__('Overtime Requests')"
			:fields="OVERTIME_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"
import { inject } from "vue"

const __ = inject("$translate")
const OVERTIME_REQUEST_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"overtime_date",
	"requested_hours",
	"status",
]

const FILTER_CONFIG = [
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: ["Draft", "Open", "Approved", "Rejected", "Cancelled"],
	},
	{
		fieldname: "employee",
		fieldtype: "Link",
		label: __("Employee"),
		options: "Employee",
	},
	{
		fieldname: "department",
		fieldtype: "Link",
		label: __("Department"),
		options: "Department",
	},
]
</script>
