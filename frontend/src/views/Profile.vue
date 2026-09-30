<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<header class="rounded-b-[32px] bg-brand-roots px-4 pb-5 pt-[max(16px,env(safe-area-inset-top))] text-brand-sand">
				<div class="flex items-center justify-between">
					<button type="button" class="flex h-11 w-11 items-center justify-center rounded-[14px] bg-brand-sand/[.08]" :aria-label="__('Back')" @click="goBack">
						<AppIcon name="back" />
					</button>
					<span class="text-base font-semibold">{{ __("Profile") }}</span>
					<span class="w-11" />
				</div>

				<div class="mt-3 flex flex-col items-center text-center">
					<span
						class="flex h-[92px] w-[92px] items-center justify-center overflow-hidden rounded-[30px] bg-brand-emerald text-[36px] font-bold shadow-[0_0_0_3px_rgb(var(--ms-roots-rgb,14,59,46)),0_0_0_5px_rgba(var(--ms-mint-rgb,52,211,153),0.55)]"
					>
						<img v-if="user.data?.user_image" :src="user.data.user_image" :alt="employee.data?.employee_name" class="h-full w-full object-cover" />
						<span v-else>{{ Array.from(employee.data?.employee_name || "?")[0] }}</span>
					</span>
					<h1 class="mt-3.5 text-[22px] font-bold">{{ employee.data?.employee_name }}</h1>
					<div class="mt-0.5 text-sm text-brand-sand/70">
						{{ [__(employee.data?.designation), __(departmentName)].filter(Boolean).join(" · ") }}
					</div>
					<span dir="ltr" class="ms-chip mt-2.5 bg-brand-mint/[.12] text-brand-mint">{{ employee.data?.name }}</span>
				</div>

				<div class="mt-[18px] grid grid-cols-3 rounded-[20px] border border-brand-mint/[.18] bg-brand-sand/[.06] py-3 text-center">
					<div v-for="(stat, index) in stats" :key="stat.label" :class="index === 1 && 'border-x border-brand-sand/[.12]'">
						<div class="text-[19px] font-bold">{{ stat.value }}</div>
						<div class="text-xs text-brand-sand/70">{{ stat.label }}</div>
					</div>
				</div>
			</header>

			<h2 class="ms-group-title mx-4 mb-2.5 mt-5">{{ __("My details") }}</h2>
			<nav class="ms-card mx-4 px-3.5" :aria-label="__('My details')">
				<button v-for="link in profileLinks" :key="link.title" type="button" class="ms-list-row" @click="openInfoModal(link)">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon :name="link.icon" :size="20" /></span>
					<span class="grow text-[15px] font-medium text-brand-ink">{{ link.title }}</span>
					<AppIcon name="forward" :size="18" class="text-brand-muted" />
				</button>
			</nav>

			<h2 class="ms-group-title mx-4 mb-2.5 mt-5">{{ __("Preferences") }}</h2>
			<div class="ms-card mx-4 px-3.5">
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
						<span class="block text-[15px] font-medium text-brand-ink">{{ __("Push notifications") }}</span>
						<span v-if="push.description.value" class="block text-xs text-brand-muted">{{ push.description.value }}</span>
					</span>
					<button
						type="button"
						role="switch"
						:aria-checked="Boolean(push.enabled.value)"
						:aria-label="__('Push notifications')"
						class="relative h-8 w-[52px] shrink-0 rounded-full transition disabled:opacity-50"
						:class="push.enabled.value ? 'bg-brand-emerald' : 'bg-brand-roots/[.18]'"
						:disabled="push.disabled.value"
						@click="push.toggle(!push.enabled.value)"
					>
						<span
							class="absolute top-[3px] h-[26px] w-[26px] rounded-full bg-white shadow transition-all"
							:class="push.enabled.value ? 'end-[3px]' : 'start-[3px]'"
						/>
					</button>
				</div>

				<router-link :to="{ name: 'ChangePassword' }" class="ms-list-row">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon name="lock" :size="20" /></span>
					<span class="grow text-[15px] font-medium text-brand-ink">{{ __("Change Password") }}</span>
					<AppIcon name="forward" :size="18" class="text-brand-muted" />
				</router-link>

				<button v-if="!install.standalone" type="button" class="ms-list-row" @click="install.open = true">
					<span class="ms-icon-tile h-[38px] w-[38px] rounded-xl bg-brand-sand text-brand-emerald"><AppIcon name="device" :size="20" /></span>
					<span class="grow text-[15px] font-medium text-brand-ink">{{ __("Install the app on your phone") }}</span>
					<AppIcon name="forward" :size="18" class="text-brand-muted" />
				</button>
			</div>

			<button
				type="button"
				class="mx-4 mt-5 flex h-[54px] w-[calc(100%-2rem)] items-center justify-center gap-2 rounded-[18px] border-[1.5px] border-state-danger/[.28] bg-white text-[15.5px] font-bold text-state-danger-text"
				@click="logout"
			>
				<AppIcon name="log-out" :size="20" />
				{{ __("Log Out") }}
			</button>

			<div class="ms-caption mb-8 mt-5 text-center">{{ brand.app_title }} · Digital Roots Solutions</div>

			<ion-modal :is-open="isInfoModalOpen" :initial-breakpoint="1" :breakpoints="[0, 1]" class="ms-sheet" @didDismiss="closeInfoModal">
				<ProfileInfoModal
					v-if="selectedItem"
					:title="selectedItem.title"
					:data="
						selectedItem.fields.map((field) => {
							const [label, fieldtype] = getFieldInfo(field)
							return {
								fieldname: field,
								value: getFieldValue(field),
								label: label,
								fieldtype: fieldtype,
							}
						})
					"
				/>
			</ion-modal>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref, watch, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent, IonModal } from "@ionic/vue"
import { createDocumentResource, createResource } from "frappe-ui"

import AppIcon from "@/components/ui/AppIcon.vue"
import ProfileInfoModal from "@/components/ProfileInfoModal.vue"

import { showErrorAlert } from "@/utils/dialogs"
import { formatCurrency, formatNumber } from "@/utils/formatters"
import { brand, languages } from "@/data/brand"
import { home } from "@/data/pwa"
import { leaveBalance } from "@/data/leaves"
import { install } from "@/data/ui"
import { usePushNotifications } from "@/composables/pushNotifications"
import { useLanguage } from "@/composables/language"

const DOCTYPE = "Employee"

const socket = inject("$socket")
const session = inject("$session")
const user = inject("$user")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")

const router = useRouter()
const push = usePushNotifications()
const language = useLanguage()

function goBack() {
	if (window.history.state?.back) router.back()
	else router.replace("/home")
}

const profileLinks = [
	{
		icon: "user",
		title: __("Employee Details"),
		fields: ["employee_name", "employee_number", "gender", "date_of_birth", "date_of_joining", "blood_group"],
	},
	{
		icon: "briefcase",
		title: __("Company Information"),
		fields: ["company", "department", "designation", "branch", "grade", "reports_to", "employment_type"],
	},
	{
		icon: "phone",
		title: __("Contact Information"),
		fields: ["cell_number", "personal_email", "company_email", "preferred_email"],
	},
	{
		icon: "banknote",
		title: __("Salary Information"),
		fields: [
			"ctc",
			"payroll_cost_center",
			"pan_number",
			"provident_fund_account",
			"salary_mode",
			"bank_name",
			"bank_ac_no",
			"ifsc_code",
			"micr_code",
			"iban",
		],
	},
]

const isInfoModalOpen = ref(false)
const selectedItem = ref(null)

const openInfoModal = async (request) => {
	selectedItem.value = request
	isInfoModalOpen.value = true
}

const closeInfoModal = async () => {
	isInfoModalOpen.value = false
	selectedItem.value = null
}

const employeeDoc = createDocumentResource({
	doctype: DOCTYPE,
	name: employee.data.name,
	fields: "*",
	auto: true,
	transform: (data) => {
		data.ctc = formatCurrency(data.ctc, data.salary_currency)
		return data
	},
})

const reportsToName = createResource({
	url: "hrms.api.get_reports_to_employee_name",
})

watch(
	() => employeeDoc.doc?.reports_to,
	(reports_to) => {
		if (reports_to) {
			reportsToName.submit({ employee: reports_to })
		}
	}
)

const employeeDocType = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: DOCTYPE },
	auto: true,
})

const getFieldInfo = (fieldname) => {
	const field = employeeDocType.data.find((field) => field.fieldname === fieldname)
	return [__(field?.label, null, "Employee"), field?.fieldtype]
}

const getFieldValue = (fieldname) => {
	if (fieldname === "employee_number" && !employeeDoc.doc[fieldname]) {
		return employeeDoc.doc["name"]
	}
	if (fieldname === "reports_to") {
		return reportsToName.data || employeeDoc.doc[fieldname]
	}
	return employeeDoc.doc[fieldname]
}

// Department names end with the company's abbreviation ("… - GESC").
const departmentName = computed(() => (employee.data?.department || "").replace(/ - [^-]+$/, ""))

const stats = computed(() => {
	const joined = employeeDoc.doc?.date_of_joining
	const years = joined ? dayjs().diff(dayjs(joined), "month") / 12 : null
	const balances = Object.values(leaveBalance.data || {})
	const main = balances.length ? balances.reduce((a, b) => (b.allocated_leaves > a.allocated_leaves ? b : a)) : null
	const month = home.data?.month
	const rate = month?.punctuality ?? month?.attendance_rate
	return [
		{ label: __("Years of service"), value: years === null ? "–" : formatNumber(years, 1) },
		{ label: __("Leave Balance"), value: main ? formatNumber(main.balance_leaves) : "–" },
		{
			label: month?.punctuality !== null && month?.punctuality !== undefined ? __("Punctuality") : __("Attendance rate"),
			value: rate === null || rate === undefined ? "–" : `${rate}%`,
		},
	]
})

const logout = async () => {
	try {
		await session.logout.submit()
	} catch (e) {
		const msg = "An error occurred while attempting to log out!"
		console.error(msg, e)
		showErrorAlert(msg)
	}
}

function onListUpdate(data) {
	if (data.doctype === DOCTYPE && data.name === employee.data.name) {
		employeeDoc.reload()
	}
}

onMounted(() => {
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", onListUpdate)
	if (!home.data) home.reload()
})

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update", onListUpdate)
})
</script>
