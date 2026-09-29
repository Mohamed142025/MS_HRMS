const routes = [
	{
		name: "PermissionRequestListView",
		path: "/permission-requests",
		component: () => import("@/views/permission_request/List.vue"),
	},
	{
		name: "PermissionRequestNewView",
		path: "/permission-requests/new",
		component: () => import("@/views/permission_request/List.vue"),
	},
	{
		name: "PermissionRequestFormView",
		path: "/permission-requests/create",
		component: () => import("@/views/permission_request/Form.vue"),
	},
	{
		name: "PermissionRequestDetailView",
		path: "/permission-requests/:id",
		props: true,
		component: () => import("@/views/permission_request/Form.vue"),
	},
]

export default routes
