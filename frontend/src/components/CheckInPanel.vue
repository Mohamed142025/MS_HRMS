<template>
	<!-- Today on the home screen's dark header: hours worked, the shift's progress and the
	     check-in / check-out button. -->
	<section class="rounded-[24px] border border-brand-mint/[.22] bg-brand-sand/[.06] p-4" :aria-label="__('Today')">
		<div class="flex items-center justify-between gap-2">
			<span class="ms-chip bg-brand-mint/[.12] text-brand-mint">
				<span class="h-[7px] w-[7px] rounded-full bg-brand-mint" :class="state === 'in' && 'animate-pulse'" />
				{{ stateLabel }}
			</span>
			<span
				v-if="settings.data?.allow_geolocation_tracking"
				class="inline-flex items-center gap-1 text-[12.5px] text-brand-sand/70"
			>
				<AppIcon name="pin" :size="15" />
				{{ __("Location is recorded") }}
			</span>
		</div>

		<div class="mt-3.5 flex items-end justify-between gap-3">
			<div>
				<div class="text-[12.5px] text-brand-sand/70">{{ __("Hours worked today") }}</div>
				<span dir="ltr" class="ms-num inline-block text-[42px] font-bold leading-tight">{{ elapsed }}</span>
			</div>
			<div v-if="firstIn" class="pb-1.5 text-end">
				<div class="text-[12.5px] text-brand-sand/70">{{ __("Checked in") }}</div>
				<div class="text-[17px] font-semibold">{{ clock(firstIn) }}</div>
			</div>
		</div>

		<div v-if="shiftWindow" class="mt-3.5">
			<div class="h-2 overflow-hidden rounded-full bg-brand-sand/[.12]">
				<div class="h-full rounded-full bg-brand-mint transition-all" :style="{ width: `${shiftProgress}%` }" />
			</div>
			<div class="mt-1.5 flex justify-between text-xs text-brand-sand/70">
				<span>{{ clock(shiftWindow.start) }}</span>
				<span>{{ shiftNote }}</span>
				<span>{{ clock(shiftWindow.end) }}</span>
			</div>
		</div>

		<button
			v-if="settings.data?.allow_employee_checkin_from_mobile_app"
			type="button"
			class="mt-4 flex h-[54px] w-full items-center justify-center gap-2 rounded-2xl bg-brand-mint text-base font-bold text-brand-roots transition active:scale-[.98] disabled:opacity-60"
			:disabled="checkins.list.loading"
			@click="openConfirm"
		>
			<AppIcon :name="nextAction.action === 'IN' ? 'log-in' : 'log-out'" :size="20" :stroke-width="2" />
			{{ nextAction.label }}
		</button>
		<router-link
			v-if="settings.data?.allow_employee_checkin_from_mobile_app"
			:to="{ name: 'EmployeeCheckinListView' }"
			class="mt-2 flex min-h-[40px] items-center justify-center text-[13px] font-semibold text-brand-sand/70"
		>
			{{ __("View check-in history") }}
		</router-link>
	</section>

	<ion-modal
		v-if="settings.data?.allow_employee_checkin_from_mobile_app"
		:is-open="confirming"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
		class="ms-sheet"
		@didDismiss="confirming = false"
	>
		<div class="flex flex-col items-center gap-4 bg-white px-4 pb-[max(24px,env(safe-area-inset-bottom))] pt-6">
			<div class="text-center">
				<div class="ms-caption">{{ dayjs(checkinTimestamp).format("dddd D MMMM") }}</div>
				<div class="ms-num text-[40px] font-bold leading-tight text-brand-ink">
					{{ dayjs(checkinTimestamp).format("h:mm a") }}
				</div>
			</div>

			<template v-if="settings.data?.allow_geolocation_tracking">
				<span v-if="locationStatus" class="ms-caption">{{ locationStatus }}</span>
				<div class="h-[170px] w-full overflow-hidden rounded-[20px] border border-brand-roots/[.12]">
					<iframe
						width="100%"
						height="170"
						frameborder="0"
						scrolling="no"
						style="border: 0"
						:title="__('Map')"
						:src="`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=15&amp;output=embed`"
					></iframe>
				</div>
			</template>

			<button
				type="button"
				class="ms-primary-button"
				:disabled="checkins.insert.loading"
				@click="submitLog(nextAction.action)"
			>
				{{ __("Confirm {0}", [nextAction.label]) }}
			</button>
		</div>
	</ion-modal>
</template>

<script setup>
import { createListResource, toast } from "frappe-ui"
import { computed, inject, ref, onMounted, onBeforeUnmount } from "vue"
import { IonModal } from "@ionic/vue"

import AppIcon from "@/components/ui/AppIcon.vue"
import { settings } from "@/data/settings"

const DOCTYPE = "Employee Checkin"

const props = defineProps({
	// The clock the home screen ticks while it is shown (a dayjs object).
	now: { type: Object, required: true },
	// Today's shift: { name, start: "HH:mm", end: "HH:mm" }.
	shift: { type: Object, default: null },
})
const emit = defineEmits(["logged"])

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")

const confirming = ref(false)
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")

const checkins = createListResource({
	doctype: DOCTYPE,
	fields: ["name", "employee", "employee_name", "log_type", "time", "device_id"],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
})
checkins.reload()

const lastLog = computed(() => {
	if (checkins.list.loading || !checkins.data) return {}
	return checkins.data[0] || {}
})

const nextAction = computed(() => {
	return lastLog.value?.log_type === "IN"
		? { action: "OUT", label: __("Check Out") }
		: { action: "IN", label: __("Check In") }
})

const todayLogs = computed(() => (checkins.data || []).filter((log) => dayjs(log.time).isToday()))
const firstIn = computed(() => {
	const ins = todayLogs.value.filter((log) => log.log_type !== "OUT")
	return ins.length ? dayjs(ins[ins.length - 1].time) : null
})

// "in" while checked in today, "out" after checking out, "none" before the first check-in.
const state = computed(() => {
	if (!todayLogs.value.length) return "none"
	return todayLogs.value[0].log_type === "OUT" ? "out" : "in"
})

const stateLabel = computed(() => {
	if (state.value === "none" && lastLog.value?.log_type === "IN")
		return __("No check-out since {0}", [dayjs(lastLog.value.time).format("D MMM")])
	return { in: __("At work now"), out: __("Checked out"), none: __("Not checked in yet") }[state.value]
})

const elapsed = computed(() => {
	if (!firstIn.value) return "0:00:00"
	const end = state.value === "out" ? dayjs(todayLogs.value[0].time) : props.now
	const seconds = Math.max(end.diff(firstIn.value, "second"), 0)
	const pad = (value) => String(value).padStart(2, "0")
	return `${Math.floor(seconds / 3600)}:${pad(Math.floor((seconds % 3600) / 60))}:${pad(seconds % 60)}`
})

const shiftWindow = computed(() => {
	if (!props.shift) return null
	const at = (time) => dayjs(`${dayjs().format("YYYY-MM-DD")} ${time}`)
	let end = at(props.shift.end)
	const start = at(props.shift.start)
	if (!end.isAfter(start)) end = end.add(1, "day")
	return { start, end }
})

const shiftProgress = computed(() => {
	const { start, end } = shiftWindow.value
	const share = props.now.diff(start) / end.diff(start)
	return Math.round(Math.min(Math.max(share, 0), 1) * 100)
})

const shiftNote = computed(() => {
	const { start, end } = shiftWindow.value
	if (props.now.isBefore(start)) return __("Shift starts at {0}", [clock(start)])
	if (props.now.isAfter(end)) return __("Shift ended")
	const minutes = end.diff(props.now, "minute")
	return __("{0} h {1} m left", [Math.floor(minutes / 60), minutes % 60])
})

const clock = (moment) => moment.format("h:mm a")

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude

	locationStatus.value = [
		__("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
		__("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
	].join(", ")
}

function handleLocationError(error) {
	locationStatus.value = __("Unable to retrieve your location")
	if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
	if (!navigator.geolocation) {
		locationStatus.value = __("Geolocation is not supported by your current browser")
	} else {
		locationStatus.value = __("Locating...")
		navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
	}
}

function openConfirm() {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")

	if (settings.data?.allow_geolocation_tracking) {
		fetchLocation()
	}
	confirming.value = true
}

const submitLog = (logType) => {
	const actionLabel = logType === "IN" ? __("Check-in") : __("Check-out")

	checkins.insert.submit(
		{
			employee: employee.data.name,
			log_type: logType,
			time: checkinTimestamp.value,
			latitude: latitude.value,
			longitude: longitude.value,
		},
		{
			onSuccess() {
				confirming.value = false
				emit("logged")
				toast({
					title: __("Success"),
					text: __("{0} successful!", [actionLabel]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(error) {
				let messages = error.messages || []

				for (const message of messages) {
					toast({
						title: __("Error"),
						text: message || __("{0} failed!", [actionLabel]),
						icon: "alert-circle",
						position: "bottom-center",
						iconClasses: "text-red-500",
					})
				}
			},
		}
	)
}

function onListUpdate(data) {
	if (data.doctype == DOCTYPE) {
		checkins.reload()
	}
}

onMounted(() => {
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", onListUpdate)
})

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update", onListUpdate)
})
</script>
