const routes = [
	{
		name: "OvertimeRequestListView",
		path: "/overtime-requests",
		component: () => import("@/views/overtime_request/List.vue"),
	},
	{
		name: "OvertimeRequestNewView",
		path: "/overtime-requests/new",
		component: () => import("@/views/overtime_request/List.vue"),
	},
	{
		name: "OvertimeRequestFormView",
		path: "/overtime-requests/create",
		component: () => import("@/views/overtime_request/Form.vue"),
	},
	{
		name: "OvertimeRequestDetailView",
		path: "/overtime-requests/:id",
		props: true,
		component: () => import("@/views/overtime_request/Form.vue"),
	},
]

export default routes
