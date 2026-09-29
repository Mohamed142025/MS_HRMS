<template>
	<ion-page>
		<ListView
			doctype="Permission Request"
			:pageTitle="__('Permission Requests')"
			:fields="PERMISSION_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"
import { inject } from "vue"

const __ = inject("$translate")
const PERMISSION_REQUEST_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"permission_type",
	"permission_date",
	"from_time",
	"to_time",
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
