"""The employee PWA at /hrms, served by ms_hrms.

The app is ms_hrms' own build of the Frappe HR PWA (frontend/), so its screens (such as
Permission and Overtime Requests) live here and Frappe HR stays as released. It is served
through the page_renderer hook, ahead of Frappe HR's page on the same URL; until it has
been built, Frappe HR's own PWA is served.

The page carries the user's language and direction, the site's branding, and the theme
stylesheets other apps list in the ms_hrms_pwa_include_css hook. Other apps can adjust
the branding through the ms_hrms_pwa_branding hook.
"""

import json
import os
from urllib.parse import quote

import frappe
from frappe.utils.jinja_globals import bundled_asset, is_rtl
from frappe.website.page_renderers.base_renderer import BaseRenderer

TEMPLATE = "templates/ms_hrms_pwa.html"
MANIFEST_PATH = "/hrms/manifest.webmanifest"
NO_CACHE = {"Cache-Control": "no-store,no-cache,must-revalidate,max-age=0"}
# Languages offered in the app's settings and on its login page.
LANGUAGES = (("ar", "العربية"), ("en", "English"))
# Home screen icons and launch screens, made from frontend/public by
# frontend/scripts/make_pwa_images.py. Android draws its launch screen from the manifest:
# the icon on the launch screen picture's background colour.
PWA_IMAGES = "/assets/ms_hrms/pwa"
LAUNCH_BACKGROUND = "#F3EFE9"


class PWAPage(BaseRenderer):
	def can_render(self):
		return self.path == "hrms" and os.path.exists(frappe.get_app_path("ms_hrms", TEMPLATE))

	def render(self):
		if frappe.local.request.path.rstrip("/") == MANIFEST_PATH:
			return self.build_response(
				json.dumps(get_manifest(), ensure_ascii=False),
				headers={**NO_CACHE, "Content-Type": "application/manifest+json; charset=utf-8"},
			)
		html = frappe.render_template(TEMPLATE, get_context())
		return self.build_response(html, headers=NO_CACHE)


def get_context():
	brand = get_branding()
	return {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"site_name": frappe.local.site,
		"boot": _as_script_json(get_boot(brand)),
		"lang": frappe.local.lang,
		"layout_direction": "rtl" if is_rtl() else "ltr",
		"app_title": brand.app_title,
		"favicon": f"{PWA_IMAGES}/favicon-196.png",
		"theme_color": brand.theme_color,
		"status_bar_style": "black-translucent" if brand.dark_header else "default",
		"splash_dark": brand.dark_header,
		"include_css": [bundled_asset(path) for path in frappe.get_hooks("ms_hrms_pwa_include_css")],
	}


def get_boot(brand=None):
	from hrms.www.hrms import get_boot as get_hrms_boot

	boot = get_hrms_boot()
	boot.brand = brand or get_branding()
	boot.languages = [{"value": code, "label": label} for code, label in LANGUAGES]
	return boot


def get_branding():
	"""The app's name, its logo for the header (drawn on a dark bar when a theme gives
	one), its square icon, and the browser's theme colour."""
	settings = frappe.get_cached_doc("Website Settings")
	brand = frappe._dict(
		app_title=settings.app_name or "Frappe HR",
		logo=_url(settings.app_logo),
		icon=_url(settings.favicon) or "/assets/hrms/manifest/favicon-196.png",
		theme_color="#ffffff",
		dark_header=False,
	)
	for method in frappe.get_hooks("ms_hrms_pwa_branding"):
		brand.update(frappe.get_attr(method)(brand) or {})
	return brand


def get_manifest():
	brand = get_branding()
	return {
		"name": brand.app_title,
		"short_name": brand.app_title,
		"description": frappe._("Everyday HR operations at your fingertips"),
		"start_url": "/hrms",
		"scope": "/hrms",
		"display": "standalone",
		"lang": frappe.local.lang,
		"dir": "rtl" if is_rtl() else "ltr",
		"theme_color": brand.theme_color,
		"background_color": LAUNCH_BACKGROUND,
		"icons": [
			{"src": f"{PWA_IMAGES}/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
			{"src": f"{PWA_IMAGES}/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
			{"src": f"{PWA_IMAGES}/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
		],
	}


@frappe.whitelist(methods=["POST"])
def set_language(language):
	"""The signed-in user's language, chosen in the app's settings."""
	if language not in dict(LANGUAGES):
		frappe.throw(frappe._("Language not available: {0}").format(language))
	user = frappe.session.user
	frappe.db.set_value("User", user, "language", language)
	frappe.clear_cache(user=user)
	return language


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return get_boot()


def _url(path):
	return quote(path, safe="/:?=&[]") if path else None


def _as_script_json(value):
	# Safe inside a <script> element.
	return frappe.as_json(value, indent=None).replace("</", "<\\/")
