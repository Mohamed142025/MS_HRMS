<template>
	<ion-header class="ion-no-border">
		<div class="w-full bg-brand-sand">
			<div
				class="flex flex-row items-center justify-between gap-3 px-4 pb-3 pt-[max(16px,env(safe-area-inset-top))]"
			>
				<div class="flex min-w-0 flex-row items-center gap-3">
					<button type="button" class="ms-icon-button" :aria-label="__('Back')" @click="goBack">
						<AppIcon name="back" />
					</button>
					<h2 class="truncate text-[22px] font-bold text-brand-ink">{{ pageTitle }}</h2>
				</div>

				<div class="flex shrink-0 flex-row items-center gap-2">
					<button
						id="show-filter-modal"
						type="button"
						class="ms-icon-button"
						:class="areFiltersApplied && '!bg-brand-roots !text-brand-sand'"
						:aria-label="__('Filter')"
					>
						<AppIcon name="sliders" :size="20" />
					</button>
					<router-link
						v-if="createPermission?.data?.has_permission && props.doctype != 'Employee Checkin'"
						:to="{ name: `${props.doctype.replace(/\s+/g, '')}FormView` }"
						v-slot="{ navigate }"
					>
						<button
							type="button"
							class="flex h-11 items-center gap-1.5 rounded-[14px] bg-brand-emerald px-3.5 text-sm font-bold text-white"
							@click="navigate"
						>
							<AppIcon name="plus" :size="18" :stroke-width="2.2" />
							{{ __("New", null, props.doctype) }}
						</button>
					</router-link>
				</div>
			</div>
		</div>
	</ion-header>

	<ion-content>
		<ion-refresher slot="fixed" @ionRefresh="handleRefresh($event)">
			<ion-refresher-content></ion-refresher-content>
		</ion-refresher>

		<div
			class="flex flex-col items-center mb-7 px-4 pb-4 h-full w-full overflow-y-auto"
			ref="scrollContainer"
			@scroll="() => handleScroll()"
		>
			<div class="w-full">
				<TabButtons
					v-if="props.tabButtons"
					class="mt-5"
					:buttons="props.tabButtons"
					v-model="activeTab"
				/>

				<div
					class="ms-card mt-4 flex flex-col"
					v-if="!documents.loading && documents.data?.length"
				>
					<div
						class="cursor-pointer items-center justify-between border-b border-brand-roots/[.08] px-3.5 py-3 last:border-b-0"
						v-for="link in documents.data"
						:key="link.name"
					>
						<component
							v-if="props.doctype === 'Employee Checkin'"
							:is="listItemComponent[doctype]"
							:doc="link"
							:isTeamRequest="isTeamRequest"
							:workflowStateField="workflowStateField"
							@click="openRequestModal(link)"
						/>
						<router-link
							v-else
							:to="{ name: detailViewRoute, params: { id: link.name } }"
							v-slot="{ navigate }"
						>
							<component
								:is="listItemComponent[doctype]"
								:doc="link"
								:isTeamRequest="isTeamRequest"
								:workflowStateField="workflowStateField"
								@click="navigate"
							/>
						</router-link>
					</div>
				</div>
				<EmptyState
					:message="__('No {0} found', [props.doctype?.toLowerCase()])"
					v-else-if="!documents.loading"
				/>

				<!-- Loading Indicator -->
				<div v-if="documents.loading" class="flex mt-2 items-center justify-center">
					<LoadingIndicator class="w-8 h-8 text-gray-800" />
				</div>
			</div>
		</div>

		<CustomIonModal trigger="show-filter-modal">
			<!-- Filter Action Sheet -->
			<template #actionSheet>
				<ListFiltersActionSheet
					:filterConfig="filterConfig"
					@applyFilters="applyFilters"
					@clearFilters="clearFilters"
					v-model:filters="filterMap"
				/>
			</template>
		</CustomIonModal>
	</ion-content>

	<ion-modal
		ref="modal"
		:is-open="isRequestModalOpen"
		@didDismiss="closeRequestModal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<RequestActionSheet
			:fields="EMPLOYEE_CHECKIN_FIELDS"
			:showOpenForm="false"
			v-model="selectedRequest"
		/>
	</ion-modal>
</template>

<script setup>
import { useRouter } from "vue-router"
import AppIcon from "@/components/ui/AppIcon.vue"
import { inject, ref, markRaw, watch, computed, reactive, onMounted } from "vue"
import {
	modalController,
	IonHeader,
	IonContent,
	IonModal,
	IonRefresher,
	IonRefresherContent,
} from "@ionic/vue"

import { FeatherIcon, createResource, LoadingIndicator, debounce } from "frappe-ui"

import TabButtons from "@/components/TabButtons.vue"
import EmployeeCheckinItem from "@/components/EmployeeCheckinItem.vue"
import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"
import ShiftAssignmentItem from "@/components/ShiftAssignmentItem.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"
import PermissionRequestItem from "@/components/PermissionRequestItem.vue"
import OvertimeRequestItem from "@/components/OvertimeRequestItem.vue"
import EmployeeAdvanceItem from "@/components/EmployeeAdvanceItem.vue"
import ListFiltersActionSheet from "@/components/ListFiltersActionSheet.vue"
import CustomIonModal from "@/components/CustomIonModal.vue"
import RequestActionSheet from "@/components/RequestActionSheet.vue"
import { EMPLOYEE_CHECKIN_FIELDS } from "@/data/config/requestSummaryFields"

import useWorkflow from "@/composables/workflow"
import { useListUpdate } from "@/composables/realtime"

const __ = inject("$translate")
const props = defineProps({
	doctype: {
		type: String,
		required: true,
	},
	fields: {
		type: Array,
		required: true,
	},
	groupBy: {
		type: String,
		required: false,
	},
	filterConfig: {
		type: Array,
		required: true,
	},
	tabButtons: {
		type: Array,
		required: false,
	},
	pageTitle: {
		type: String,
		required: true,
	},
})

const getButtonKey = (tab) => tab?.key ?? tab

const listItemComponent = {
	"Employee Checkin": markRaw(EmployeeCheckinItem),
	"Attendance Request": markRaw(AttendanceRequestItem),
	"Shift Request": markRaw(ShiftRequestItem),
	"Shift Assignment": markRaw(ShiftAssignmentItem),
	"Leave Application": markRaw(LeaveRequestItem),
	"Expense Claim": markRaw(ExpenseClaimItem),
	"Permission Request": markRaw(PermissionRequestItem),
	"Overtime Request": markRaw(OvertimeRequestItem),
	"Employee Advance": markRaw(EmployeeAdvanceItem),
}

const router = useRouter()

function goBack() {
	if (window.history.state?.back) router.back()
	else router.replace("/home")
}
const dayjs = inject("$dayjs")
const socket = inject("$socket")
const employee = inject("$employee")
const filterMap = reactive({})
const activeTab = ref(props.tabButtons ? getButtonKey(props.tabButtons[0]) : undefined)
const areFiltersApplied = ref(false)
const appliedFilters = ref([])
const workflowStateField = ref(null)
const isRequestModalOpen = ref(false)
const selectedRequest = ref(null)

// infinite scroll
const scrollContainer = ref(null)
const hasNextPage = ref(true)
const listOptions = ref({
	doctype: props.doctype,
	fields: props.fields,
	group_by: props.groupBy,
	order_by: `\`tab${props.doctype}\`.modified desc`,
	page_length: 50,
})

// computed properties
const isTeamRequest = computed(() => {
	return props.tabButtons && activeTab.value === getButtonKey(props.tabButtons[1])
})

const formViewRoute = computed(() => {
	return `${props.doctype.replace(/\s+/g, "")}FormView`
})

const detailViewRoute = computed(() => {
	return `${props.doctype.replace(/\s+/g, "")}DetailView`
})

const defaultFilters = computed(() => {
	const filters = []

	if (useClientList.value) {
		if (isTeamRequest.value) {
			filters.push(["employee", "!=", employee.data.name])
		} else {
			filters.push(["employee", "=", employee.data.name])
		}
		return filters
	}

	if (isTeamRequest.value) {
		filters.push([props.doctype, "employee", "!=", employee.data.name])
	} else {
		filters.push([props.doctype, "employee", "=", employee.data.name])
	}

	return filters
})

// resources
const useClientList = computed(() =>
	["Permission Request", "Overtime Request"].includes(props.doctype)
)

const documents = createResource({
	url: useClientList.value ? "frappe.client.get_list" : "frappe.desk.reportview.get",
	onSuccess: (data) => {
		if (data.values?.length < listOptions.value.page_length) {
			hasNextPage.value = false
		}
	},
	transform(data) {
		if (!data || data.length === 0) {
			return []
		}

		if (useClientList.value) {
			return data
		}

		// convert keys and values arrays to docs object
		const fields = data["keys"]
		const values = data["values"]
		const docs = values.map((value) => {
			const doc = {}
			fields.forEach((field, index) => {
				doc[field] = value[index]
			})
			return doc
		})

		let pagedData
		if (!documents.params.start || documents.params.start === 0) {
			pagedData = docs
		} else {
			pagedData = documents.data.concat(docs)
		}

		return pagedData
	},
})

const createPermission = createResource({
	url: "frappe.client.has_permission",
	params: { doctype: props.doctype, docname: "", perm_type: "create" },
	auto: true,
})

// helper functions
const openRequestModal = async (request) => {
	selectedRequest.value = request
	selectedRequest.value.doctype = "Employee Checkin"
	selectedRequest.value.date = request.time
	selectedRequest.value.formatted_time = dayjs(request.time).format("HH:mm a")
	selectedRequest.value.formatted_latitude = `${Number(request.latitude).toFixed(5)}°`
	selectedRequest.value.formatted_longitude = `${Number(request.longitude).toFixed(5)}°`
	isRequestModalOpen.value = true
}

const closeRequestModal = async () => {
	isRequestModalOpen.value = false
	selectedRequest.value = null
}

function initializeFilters() {
	props.filterConfig.forEach((filter) => {
		filterMap[filter.fieldname] = {
			condition: "=",
			value: null,
		}
	})

	appliedFilters.value = []
}
initializeFilters()

function prepareFilters() {
	let condition = ""
	let value = ""
	appliedFilters.value = []

	for (const fieldname in filterMap) {
		condition = filterMap[fieldname].condition
		// accessing .value because autocomplete returns an object instead of value
		if (typeof condition === "object" && condition !== null) {
			condition = condition.value
		}

		value = filterMap[fieldname].value
		if (!condition || !value) continue

		if (useClientList.value) {
			appliedFilters.value.push([fieldname, condition, value])
		} else {
			appliedFilters.value.push([props.doctype, fieldname, condition, value])
		}
	}
}

function applyFilters() {
	prepareFilters()
	fetchDocumentList()
	modalController.dismiss()
	areFiltersApplied.value = appliedFilters.value.length ? true : false
}

function clearFilters() {
	initializeFilters()
	fetchDocumentList()
	modalController.dismiss()
	areFiltersApplied.value = false
}

function fetchDocumentList(start = 0) {
	if (start === 0) {
		hasNextPage.value = true
	}

	if (useClientList.value) {
		const filters = [["docstatus", "!=", 2]]
		filters.push(...defaultFilters.value)
		if (appliedFilters.value) filters.push(...appliedFilters.value)

		documents.submit({
			doctype: props.doctype,
			fields: props.fields,
			filters: filters,
			limit_page_length: listOptions.value.page_length,
			order_by: listOptions.value.order_by,
			start: start || 0,
		})
		return
	}

	const filters = [[props.doctype, "docstatus", "!=", "2"]]
	filters.push(...defaultFilters.value)

	if (appliedFilters.value) filters.push(...appliedFilters.value)

	if (workflowStateField.value) {
		listOptions.value.fields.push(workflowStateField.value)
	}

	documents.submit({
		...listOptions.value,
		start: start || 0,
		filters: filters,
	})
}

const handleScroll = debounce(() => {
	if (!hasNextPage.value) return

	const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value
	const scrollPercentage = (scrollTop / (scrollHeight - clientHeight)) * 100

	if (scrollPercentage >= 90) {
		const start = documents.params.start + listOptions.value.page_length
		fetchDocumentList(start)
	}
}, 500)

const handleRefresh = (event) => {
	setTimeout(() => {
		fetchDocumentList()
		event.target.complete()
	}, 500)
}

watch(
	() => activeTab.value,
	(_value) => {
		fetchDocumentList()
	}
)

onMounted(async () => {
	const workflow = useWorkflow(props.doctype)
	await workflow.workflowDoc.promise
	workflowStateField.value = workflow.getWorkflowStateField()
	fetchDocumentList()

	useListUpdate(socket, props.doctype, () => fetchDocumentList())
})
</script>
