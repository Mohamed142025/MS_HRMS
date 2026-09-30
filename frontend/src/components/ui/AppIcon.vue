<template>
	<svg
		:width="size"
		:height="size"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		:stroke-width="strokeWidth"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
		:class="flips ? 'ms-flip-rtl' : ''"
	>
		<path v-for="(d, index) in shape.paths" :key="`p${index}`" :d="d" />
		<circle v-for="(c, index) in shape.circles" :key="`c${index}`" :cx="c[0]" :cy="c[1]" :r="c[2]" />
		<rect
			v-for="(r, index) in shape.rects"
			:key="`r${index}`"
			:x="r[0]"
			:y="r[1]"
			:width="r[2]"
			:height="r[3]"
			:rx="r[4]"
		/>
	</svg>
</template>

<script setup>
import { computed } from "vue"

// The app's line icons: 24px grid, round caps. "forward", "back" and the arrows that
// point along the reading direction are drawn for left to right and mirrored in
// right to left pages.
const ICONS = {
	home: { paths: ["M3.5 10.5 12 3.5l8.5 7V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-6v6H5A1.5 1.5 0 0 1 3.5 19z"] },
	clock: { paths: ["M12 7v5l3 2"], circles: [[12, 12, 9]] },
	plus: { paths: ["M12 5v14M5 12h14"] },
	clipboard: {
		paths: ["M9 4.5V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v.5M9 11h6M9 15h4"],
		rects: [[5, 4.5, 14, 16.5, 2.5]],
	},
	wallet: {
		paths: ["M4 7.5A2.5 2.5 0 0 1 6.5 5H17v3", "M4 7.5V18a2 2 0 0 0 2 2h14V8H6.5A2.5 2.5 0 0 1 4 7.5z"],
		circles: [[16, 14, 1.3]],
	},
	bell: { paths: ["M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8", "M10.3 20a1.9 1.9 0 0 0 3.4 0"] },
	user: { paths: ["M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"], circles: [[12, 8, 4]] },
	users: {
		paths: ["M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5", "M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c1.8.8 3 2.6 3.5 5.2"],
		circles: [[9, 8, 3.5]],
	},
	calendar: { paths: ["M8 3v4M16 3v4M3.5 10h17"], rects: [[3.5, 5, 17, 16, 2.5]] },
	pin: { paths: ["M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"], circles: [[12, 9.5, 2.5]] },
	sun: {
		paths: ["M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"],
		circles: [[12, 12, 4]],
	},
	hourglass: { paths: ["M6.5 3h11M6.5 21h11", "M7.5 3v2.5a4.5 4.5 0 0 0 9 0V3M7.5 21v-2.5a4.5 4.5 0 0 1 9 0V21"] },
	"clock-plus": { paths: ["M11 9v4l2.5 1.5M19 2v5M16.5 4.5h5"], circles: [[11, 13, 8]] },
	receipt: { paths: ["M6 3h12v18l-3-2-3 2-3-2-3 2z", "M9 8h6M9 12h6M9 16h3"] },
	banknote: { paths: ["M6 9v.01M18 15v.01"], rects: [[2.5, 6, 19, 12, 2]], circles: [[12, 12, 2.5]] },
	swap: { paths: ["M4 8h13l-3-3M20 16H7l3 3"] },
	"calendar-check": { paths: ["M8 3v4M16 3v4M3.5 10h17", "M9 15l2 2 4-4"], rects: [[3.5, 5, 17, 16, 2.5]] },
	forward: { paths: ["M9 6l6 6-6 6"], flips: true },
	back: { paths: ["M15 6l-6 6 6 6"], flips: true },
	down: { paths: ["M6 9l6 6 6-6"] },
	check: { paths: ["M5 12.5l4.5 4.5L19 7.5"] },
	x: { paths: ["M6 6l12 12M18 6L6 18"] },
	bulb: {
		paths: ["M9 18h6M10 21h4", "M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"],
	},
	"trend-up": { paths: ["M3 17l6-6 4 4 8-8", "M15 7h6v6"], flips: true },
	file: { paths: ["M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z", "M14 3v5h5M9 13h6M9 17h4"] },
	download: { paths: ["M12 4v11M7 10l5 5 5-5M5 20h14"] },
	share: {
		paths: [
			"M12 3v12M8 7l4-4 4 4",
			"M8 10H6.5A1.5 1.5 0 0 0 5 11.5v8A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5v-8a1.5 1.5 0 0 0-1.5-1.5H16",
		],
	},
	eye: { paths: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"], circles: [[12, 12, 3]] },
	"eye-off": {
		paths: [
			"M3 3l18 18",
			"M10.6 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.9 3.8M6.6 6.6C3.7 8.5 2 12 2 12s3.5 7 10 7c1.9 0 3.5-.5 4.9-1.3",
			"M9.9 9.9a3 3 0 0 0 4.2 4.2",
		],
	},
	lock: { paths: ["M8 10.5V7a4 4 0 0 1 8 0v3.5"], rects: [[4.5, 10.5, 15, 10.5, 2.5]] },
	mail: { paths: ["M3.5 6.5 12 13l8.5-6.5"], rects: [[3, 5, 18, 14, 2.5]] },
	globe: {
		paths: ["M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"],
		circles: [[12, 12, 9]],
	},
	"log-out": { paths: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5M21 12H9"], flips: true },
	"log-in": { paths: ["M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4", "M10 17l5-5-5-5M15 12H3"], flips: true },
	phone: {
		paths: ["M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"],
	},
	briefcase: {
		paths: ["M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 12.5h18"],
		rects: [[3, 7, 18, 13, 2.5]],
	},
	sliders: { paths: ["M4 7h10M18 7h2M4 17h4M12 17h8"], circles: [[16, 7, 2], [10, 17, 2]] },
	search: { paths: ["M20 20l-3.5-3.5"], circles: [[11, 11, 7]] },
	alert: { paths: ["M12 8v5M12 16.5v.01"], circles: [[12, 12, 9]] },
	chart: { paths: ["M6 20v-6M12 20V6M18 20v-9"] },
	device: { paths: ["M11 18.5h2"], rects: [[6.5, 2.5, 11, 19, 2.5]] },
	"plus-square": { paths: ["M12 8v8M8 12h8"], rects: [[4, 4, 16, 16, 4]] },
	refresh: { paths: ["M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4", "M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4"] },
	upload: { paths: ["M12 16V4M7 9l5-5 5 5", "M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4"] },
	more: { circles: [[5, 12, 1], [12, 12, 1], [19, 12, 1]] },
}

const props = defineProps({
	name: { type: String, required: true },
	size: { type: [Number, String], default: 22 },
	strokeWidth: { type: [Number, String], default: 1.8 },
})

const shape = computed(() => ({ paths: [], circles: [], rects: [], ...(ICONS[props.name] || ICONS.more) }))
const flips = computed(() => Boolean(shape.value.flips))
</script>
