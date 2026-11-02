// The employee's own evaluations (ms_hrms.my_evaluations).
const routes = [
	{
		path: "/evaluations",
		name: "EmployeeEvaluationListView",
		component: () => import("@/views/evaluation/List.vue"),
	},
	{
		path: "/evaluations/:id",
		name: "EmployeeEvaluationDetailView",
		props: true,
		component: () => import("@/views/evaluation/Detail.vue"),
	},
]

export default routes
