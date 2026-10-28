<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<SubHeader :title="__('Not in yet')" :subtitle="subtitle" fallback="/home" />

			<div v-if="board.error" class="ms-caption mx-4 mt-6 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center">
				{{ __("You are not allowed to see who has checked in.") }}
			</div>
			<div v-else-if="!data" class="ms-caption p-10 text-center">{{ __("Loading...") }}</div>
			<template v-else>
				<!-- The day so far -->
				<div class="mx-4 mt-4 grid grid-cols-4 gap-2">
					<div v-for="tile in tiles" :key="tile.key" class="ms-card px-2.5 py-3 text-center">
						<div class="ms-num text-[20px] font-bold text-brand-ink">{{ tile.count }}</div>
						<div class="truncate text-[11.5px] text-brand-muted">{{ tile.label }}</div>
					</div>
				</div>

				<div class="hide-scrollbar mt-4 flex gap-2 overflow-x-auto px-4">
					<button
						v-for="tab in tabs"
						:key="tab.value"
						type="button"
						class="ms-filter-chip"
						:class="list === tab.value && 'is-active'"
						:aria-pressed="list === tab.value"
						@click="list = tab.value"
					>
						{{ tab.label }}
						<span class="ms-num opacity-60">{{ tab.count }}</span>
					</button>
				</div>

				<label class="relative mx-4 mt-3 block">
					<span class="sr-only">{{ __("Search by employee name") }}</span>
					<AppIcon name="search" :size="18" class="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-brand-muted" />
					<input
						v-model.trim="search"
						type="search"
						class="ms-field ps-10 pe-10"
						:placeholder="__('Search by employee name')"
						enterkeyhint="search"
					/>
					<button
						v-if="search"
						type="button"
						class="absolute end-1 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center text-brand-muted"
						:aria-label="__('Clear')"
						@click="search = ''"
					>
						<AppIcon name="x" :size="18" />
					</button>
				</label>

				<div v-if="departments.length > 1" class="hide-scrollbar mt-3 flex gap-2 overflow-x-auto px-4">
					<button
						v-for="item in [{ value: '', label: __('All departments') }, ...departments]"
						:key="item.value"
						type="button"
						class="ms-filter-chip"
						:class="department === item.value && 'is-active'"
						:aria-pressed="department === item.value"
						@click="department = item.value"
					>
						{{ item.label }}
					</button>
				</div>

				<p v-if="list === 'no_shift'" class="ms-caption mx-4 mt-3">
					{{ __("These employees have no shift assigned and no default shift, so whether they came in is not followed.") }}
				</p>

				<div v-if="shown.length" class="ms-card mx-4 mb-8 mt-3 px-3.5">
					<div v-for="person in shown" :key="person.employee" class="ms-list-row">
						<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-emerald text-[17px] font-bold text-white">
							{{ Array.from(person.employee_name || "?")[0] }}
						</span>
						<span class="min-w-0 grow">
							<span class="block break-words text-[15px] font-semibold leading-6 text-brand-ink">{{ person.employee_name }}</span>
							<span class="block truncate text-[12.5px] text-brand-muted">{{ details(person) }}</span>
							<span v-if="lateness(person)" class="block truncate text-[12.5px] font-semibold" :class="person.permission_until ? 'text-state-warning-text' : 'text-state-danger-text'">
								{{ lateness(person) }}
							</span>
						</span>
						<template v-if="person.phone">
							<a :href="`tel:${person.phone}`" class="ms-icon-button bg-brand-emerald text-white" :aria-label="__('Call {0}', [person.employee_name])">
								<AppIcon name="phone" :size="20" />
							</a>
							<a
								v-if="whatsapp(person.phone)"
								:href="whatsapp(person.phone)"
								target="_blank"
								rel="noopener"
								class="ms-icon-button text-state-success-text"
								:aria-label="__('WhatsApp {0}', [person.employee_name])"
							>
								<AppIcon name="chat" :size="20" />
							</a>
						</template>
						<span v-else class="ms-caption shrink-0">{{ __("No number") }}</span>
					</div>
				</div>
				<div v-else class="ms-caption mx-4 mb-8 mt-3 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center">
					{{ emptyText }}
				</div>
			</template>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"

import SubHeader from "@/components/ui/SubHeader.vue"
import AppIcon from "@/components/ui/AppIcon.vue"
import { attendanceBoard as board } from "@/data/pwa"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

// Kept current while the screen is open.
const REFRESH_MINUTES = 3
let timer = null
onMounted(() => {
	board.reload()
	timer = setInterval(() => board.reload(), REFRESH_MINUTES * 60 * 1000)
})
onBeforeUnmount(() => timer && clearInterval(timer))

async function refresh(event) {
	await board.reload()
	event.target.complete()
}

const data = computed(() => board.data)
const clock = (time) => (time ? dayjs(`2000-01-01 ${time}`).format("h:mm a") : "")
const subtitle = computed(() => (data.value ? __("Today · as of {0}", [clock(data.value.as_of)]) : ""))

const tiles = computed(() => {
	const counts = data.value?.counts || {}
	return [
		{ key: "present", label: __("Present"), count: counts.present || 0 },
		{ key: "upcoming", label: __("Not started yet"), count: counts.upcoming || 0 },
		{ key: "on_leave", label: __("On Leave"), count: (counts.on_leave || 0) + (counts.on_duty || 0) },
		{ key: "holiday", label: __("Holiday"), count: counts.holiday || 0 },
	]
})

// The lists: who has not come in, who is absent (their shift ended), who has a late
// arrival permission, and who has no shift. Absent shows only when someone is.
const tabs = computed(() => {
	const lists = data.value || {}
	return [
		{ value: "not_in", label: __("Not in yet"), count: lists.not_in?.length || 0 },
		...(lists.absent?.length ? [{ value: "absent", label: __("Absent"), count: lists.absent.length }] : []),
		{ value: "permission", label: __("Late arrival permission"), count: lists.permission?.length || 0 },
		{ value: "no_shift", label: __("No shift"), count: lists.no_shift?.length || 0 },
	]
})
const list = ref("not_in")
// Opened after the shifts ended: start on who was absent.
watch(data, (value, before) => {
	if (!before && value && !value.not_in?.length && value.absent?.length) list.value = "absent"
})

const search = ref("")
const department = ref("")
const people = computed(() => data.value?.[list.value] || [])
const departments = computed(() =>
	[...new Set(people.value.map((person) => person.department).filter(Boolean))]
		.sort()
		.map((value) => ({ value, label: value.replace(/ - [^-]+$/, "") }))
)
watch(list, () => (department.value = ""))

const shown = computed(() => {
	const words = search.value.toLowerCase().split(/\s+/).filter(Boolean)
	return people.value.filter((person) => {
		if (department.value && person.department !== department.value) return false
		const name = `${person.employee_name || ""} ${person.employee}`.toLowerCase()
		return words.every((word) => name.includes(word))
	})
})

const emptyText = computed(() => {
	if (search.value || department.value) return __("No employees match these filters")
	return {
		not_in: __("Everyone whose shift started has checked in"),
		absent: __("No one is absent"),
		permission: __("No late arrival permissions today"),
		no_shift: __("Every employee has a shift"),
	}[list.value]
})

const department_name = (value) => (value || "").replace(/ - [^-]+$/, "")
function details(person) {
	// Shift names are the site's own, shown as they are.
	const shift = person.shift ? `${person.shift} · ${clock(person.shift_start)}` : ""
	return [department_name(person.department), shift].filter(Boolean).join(" · ")
}

function lateness(person) {
	if (person.permission_until) return __("Permission until {0}", [clock(person.permission_until)])
	const minutes = person.minutes_late
	if (!minutes) return ""
	if (minutes < 60) return __("{0} min late", [minutes])
	return __("{0} h {1} min late", [Math.floor(minutes / 60), minutes % 60])
}

// WhatsApp needs the number with its country code: Egyptian mobiles (01…) get +20.
function whatsapp(phone) {
	let digits = (phone || "").replace(/[^\d+]/g, "")
	if (digits.startsWith("+")) digits = digits.slice(1)
	else if (digits.startsWith("00")) digits = digits.slice(2)
	else if (/^01\d{9}$/.test(digits)) digits = `20${digits.slice(1)}`
	return digits.length >= 10 ? `https://wa.me/${digits}` : ""
}
</script>
