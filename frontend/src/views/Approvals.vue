<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<ion-refresher slot="fixed" @ionRefresh="refresh">
				<ion-refresher-content />
			</ion-refresher>

			<PageHeader :title="__('Requests')" :subtitle="__('Leaves, permissions, overtime and expenses')" />

			<Segmented class="mx-4 mt-4" :options="tabs" model-value="approvals" />

			<section v-if="team?.size" class="ms-card mx-4 mt-4 p-4" :aria-label="__('Your team today')">
				<div class="flex items-center justify-between">
					<h2 class="text-[15.5px] font-bold text-brand-ink">{{ __("Your team today") }}</h2>
					<span class="ms-caption">{{ __("{0} employees · as of {1}", [team.size, clock(team.as_of)]) }}</span>
				</div>
				<div class="mt-3 flex h-2.5 gap-0.5 overflow-hidden rounded-full">
					<span v-for="part in teamParts.filter((p) => p.count)" :key="part.key" :class="part.bar" :style="{ flexGrow: part.count }" />
				</div>
				<div class="mt-3 grid grid-cols-4 gap-1.5">
					<div v-for="part in teamParts" :key="part.key">
						<div class="text-[20px] font-bold text-brand-ink">{{ part.count }}</div>
						<div class="flex items-center gap-1 text-xs text-brand-muted">
							<span class="h-2 w-2 shrink-0 rounded-full" :class="part.bar" />
							<span class="truncate">{{ part.label }}</span>
						</div>
					</div>
				</div>
				<div v-if="team.on_leave?.length || team.late?.length" class="mt-3 border-t border-brand-roots/[.08] pt-3 text-[13px] leading-6 text-brand-ink/80">
					<div v-if="team.on_leave?.length">
						<span class="font-semibold">{{ __("On leave today:") }}</span> {{ team.on_leave.map((p) => p.employee_name).join("، ") }}
					</div>
					<div v-if="team.late?.length">
						<span class="font-semibold">{{ __("Late today:") }}</span> {{ team.late.map((p) => p.employee_name).join("، ") }}
					</div>
				</div>
			</section>

			<h2 class="ms-group-title mx-4 mb-2.5 mt-5">{{ __("Awaiting your approval · {0}", [pending.length]) }}</h2>

			<div v-if="pending.length" class="mx-4 mb-8 flex flex-col gap-2.5">
				<article v-for="doc in pending" :key="`${doc.doctype}:${doc.name}`" class="ms-card p-3.5">
					<button type="button" class="flex w-full items-center gap-3 text-start" @click="selected = doc">
						<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-emerald text-[17px] font-bold text-white">
							{{ Array.from(doc.employee_name || "?")[0] }}
						</span>
						<span class="min-w-0 grow">
							<span class="block truncate text-[15px] font-bold text-brand-ink">{{ doc.employee_name }}</span>
							<span class="block truncate text-[12.5px] text-brand-muted">{{ dayjs(doc.creation).fromNow() }}</span>
						</span>
						<span class="ms-chip" :class="TONES[REQUEST_TYPES[doc.doctype].tone]">{{ typeLabel(doc.doctype) }}</span>
					</button>

					<button type="button" class="mt-3 block w-full rounded-2xl bg-brand-sand/60 px-3 py-2.5 text-start text-sm leading-6" @click="selected = doc">
						<span class="block font-bold text-brand-ink">{{ requestTitle(doc) }} · {{ requestDetails(doc) }}</span>
						<span v-if="reason(doc)" class="block text-brand-muted">{{ reason(doc) }}</span>
					</button>

					<div v-if="state[key(doc)]?.decided" class="mt-3 flex items-center gap-2">
						<StatusChip :status="state[key(doc)].decided" />
						<button
							v-if="state[key(doc)].canSubmit"
							type="button"
							class="ms-primary-button h-11 grow text-sm"
							:disabled="state[key(doc)].busy"
							@click="submitDoc(doc)"
						>
							{{ __("Submit") }}
						</button>
						<span v-else class="ms-caption">{{ __("Decision saved") }}</span>
					</div>

					<div v-else-if="workflowDoctypes.has(doc.doctype)" class="mt-3">
						<button type="button" class="ms-secondary-button w-full" @click="selected = doc">{{ __("Review request") }}</button>
					</div>

					<div v-else-if="!approvalFlow(doc.doctype).field" class="mt-3">
						<button type="button" class="ms-primary-button h-[46px] text-[14.5px]" :disabled="state[key(doc)]?.busy" @click="submitDoc(doc)">
							{{ __("Approve") }}
						</button>
					</div>

					<div v-else class="mt-3 grid grid-cols-2 gap-2">
						<button
							type="button"
							class="h-[46px] rounded-[14px] border-[1.5px] border-state-danger/[.28] bg-white text-[14.5px] font-bold text-state-danger-text disabled:opacity-60"
							:disabled="state[key(doc)]?.busy"
							@click="decideDoc(doc, 'Rejected')"
						>
							{{ __("Reject") }}
						</button>
						<button
							type="button"
							class="h-[46px] rounded-[14px] bg-brand-emerald text-[14.5px] font-bold text-white disabled:opacity-60"
							:disabled="state[key(doc)]?.busy"
							@click="decideDoc(doc, 'Approved')"
						>
							{{ __("Approve") }}
						</button>
					</div>
				</article>
			</div>
			<div v-else class="ms-caption mx-4 mb-8 rounded-[22px] border-[1.5px] border-dashed border-brand-roots/[.12] p-8 text-center">
				{{ __("No requests are waiting for your approval") }}
			</div>

			<RequestSheet :request="selected" @close="onSheetClosed" />
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, markRaw, onMounted, reactive, ref, shallowReactive, watch } from "vue"
import { IonPage, IonContent, IonRefresher, IonRefresherContent } from "@ionic/vue"
import { toast } from "frappe-ui"

import PageHeader from "@/components/ui/PageHeader.vue"
import Segmented from "@/components/ui/Segmented.vue"
import StatusChip from "@/components/ui/StatusChip.vue"
import RequestSheet from "@/components/RequestSheet.vue"

import { teamToday } from "@/data/pwa"
import { teamLeaves } from "@/data/leaves"
import { teamClaims } from "@/data/claims"
import {
	teamShiftRequests,
	teamAttendanceRequests,
	teamPermissionRequests,
	teamOvertimeRequests,
} from "@/data/attendance"
import { approvalFlow, canSubmit, decide, submit } from "@/composables/approval"
import useWorkflow from "@/composables/workflow"
import { REQUEST_TYPES, TONES, requestDetails, requestTitle, typeLabel } from "@/utils/requestTypes"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const sources = {
	"Leave Application": teamLeaves,
	"Expense Claim": teamClaims,
	"Permission Request": teamPermissionRequests,
	"Overtime Request": teamOvertimeRequests,
	"Shift Request": teamShiftRequests,
	"Attendance Request": teamAttendanceRequests,
}

onMounted(() => teamToday.reload())

// Requests decided here stay on screen until the next refresh, so a decision that is
// followed by submitting can be submitted.
const state = reactive({})
const key = (doc) => `${doc.doctype}:${doc.name}`
const kept = reactive({})

async function refresh(event) {
	for (const name of Object.keys(kept)) delete kept[name]
	for (const name of Object.keys(state)) delete state[name]
	await Promise.allSettled([teamToday.reload(), ...Object.values(sources).map((resource) => resource.reload())])
	event.target.complete()
}


const pending = computed(() => {
	const current = Object.values(sources).flatMap((resource) => resource.data || [])
	const names = new Set(current.map(key))
	const decided = Object.values(kept).filter((doc) => !names.has(key(doc)))
	return [...current, ...decided].sort((a, b) => new Date(b.creation) - new Date(a.creation))
})

const tabs = computed(() => [
	{ value: "mine", label: __("My Requests"), to: { name: "Requests" } },
	{ value: "approvals", label: __("For approval"), to: { name: "Approvals" }, badge: pending.value.length || "" },
])

// Doctypes with an active workflow are decided through their workflow actions (looked
// up only for the doctypes that have requests waiting).
const workflows = shallowReactive({})
watch(
	() => [...new Set(pending.value.map((doc) => doc.doctype))],
	(doctypes) => {
		for (const doctype of doctypes) if (!workflows[doctype]) workflows[doctype] = markRaw(useWorkflow(doctype))
	},
	{ immediate: true }
)
const workflowDoctypes = computed(
	() => new Set(Object.keys(workflows).filter((doctype) => workflows[doctype].hasWorkflow.value))
)

const reason = (doc) => doc.reason || doc.description || doc.explanation || ""

function notify(ok, text) {
	toast({
		title: ok ? __("Success") : __("Error"),
		text,
		icon: ok ? "check-circle" : "alert-circle",
		position: "bottom-center",
		iconClasses: ok ? "text-green-500" : "text-red-500",
	})
}

async function decideDoc(doc, decision) {
	const entry = (state[key(doc)] = { busy: true })
	try {
		await decide(doc, decision)
		kept[key(doc)] = doc
		entry.decided = decision
		entry.canSubmit = approvalFlow(doc.doctype).submitAfter && (await canSubmit(doc))
		notify(true, __("{0} successfully!", [__(decision)]))
		sources[doc.doctype].reload()
	} catch (error) {
		notify(false, error.messages?.[0] || __("{0} failed!", [decision === "Approved" ? __("Approval") : __("Rejection")]))
	} finally {
		entry.busy = false
	}
}

async function submitDoc(doc) {
	const entry = (state[key(doc)] ||= {})
	entry.busy = true
	try {
		await submit(doc)
		delete kept[key(doc)]
		delete state[key(doc)]
		notify(true, __("Document {0} successfully!", [__("submitted")]))
		sources[doc.doctype].reload()
	} catch (error) {
		notify(false, error.messages?.[0] || __("Document {0} failed!", [__("submission")]))
		entry.busy = false
	}
}

const teamParts = computed(() => {
	const counts = teamToday.data?.counts || {}
	return [
		{ key: "on_time", label: __("Present"), count: counts.on_time || 0, bar: "bg-state-success" },
		{ key: "late", label: __("Late"), count: counts.late || 0, bar: "bg-state-warning" },
		{ key: "on_leave", label: __("On Leave"), count: counts.on_leave || 0, bar: "bg-state-info" },
		{ key: "not_in", label: __("Not checked in"), count: counts.not_in || 0, bar: "bg-brand-roots/[.18]" },
	]
})
const team = computed(() => teamToday.data)
const clock = (time) => (time ? dayjs(`2000-01-01 ${time}`).format("h:mm a") : "")

const selected = ref(null)
function onSheetClosed() {
	const doc = selected.value
	selected.value = null
	if (doc) sources[doc.doctype]?.reload()
}
</script>
