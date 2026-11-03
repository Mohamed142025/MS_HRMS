// HR's announcements, with their formatting (ms_hrms.app_notifications.get_announcement).
const routes = [
	{
		path: "/announcements/:id",
		name: "HRAnnouncementDetailView",
		props: true,
		component: () => import("@/views/Announcement.vue"),
	},
]

export default routes
