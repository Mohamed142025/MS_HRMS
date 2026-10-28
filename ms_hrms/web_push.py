"""Push notifications to the employee app, sent from this site (Web Push, VAPID).

Every notification the app lists (PWA Notification) is also pushed to the devices of its
user that turned notifications on in the app's settings (Push Subscription). The site's
VAPID keys are made by setup() on migrate, so the app's push notifications work on any
site with ms_hrms, without Frappe's push relay; the private key is kept encrypted. When
the keys have to be made again (the site's encryption key changed), the devices
subscribed with the old ones are dropped and turn notifications on again.

A push goes from the site to the browser's own push service (Google's for Chrome on
Android, Apple's for an iPhone's home screen app), which delivers it to the device. Sites
must be served over HTTPS.
"""

import base64
import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, strip_html
from frappe.utils.password import get_decrypted_password, set_encrypted_password

PUBLIC_KEY = "ms_hrms_vapid_public_key"
KEY_DOCTYPE = "Push Subscription"
KEY_NAME = "VAPID"
KEY_FIELD = "private_key"
# Kept by the push service while the device is off, at most a day.
TTL_SECONDS = 24 * 60 * 60

# Where a notification opens in the app, by what it is about.
ROUTES = {
	"Leave Application": "leave-applications/{name}",
	"Expense Claim": "expense-claims/{name}",
	"Shift Request": "shift-requests/{name}",
	"Attendance Request": "attendance-requests/{name}",
	"Permission Request": "permission-requests/{name}",
	"Overtime Request": "overtime-requests/{name}",
	"Employee Advance": "employee-advances/{name}",
	"Salary Slip": "salary-slips/{name}",
	"Shift Type": "not-checked-in",
	"Employee Checkin": "home",
}


# Keys


def setup():
	get_keys()


def get_keys():
	"""The site's VAPID keys as (public key for the browser, private key PEM), made when
	missing or no longer readable."""
	public = frappe.db.get_default(PUBLIC_KEY)
	private = _private_key()
	if public and private:
		return public, private
	return _make_keys()


def _private_key():
	try:
		return get_decrypted_password(KEY_DOCTYPE, KEY_NAME, KEY_FIELD, raise_exception=False)
	except Exception:
		# Encrypted with another encryption key: unreadable.
		return None


def _make_keys():
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import ec

	key = ec.generate_private_key(ec.SECP256R1())
	private = key.private_bytes(
		serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
	).decode()
	point = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
	public = base64.urlsafe_b64encode(point).rstrip(b"=").decode()

	# Devices subscribed with other keys cannot be sent to any more.
	frappe.db.delete("Push Subscription")
	set_encrypted_password(KEY_DOCTYPE, KEY_NAME, private, KEY_FIELD)
	frappe.db.set_default(PUBLIC_KEY, public)
	return public, private


# The app's settings


@frappe.whitelist()
def get_public_key():
	return get_keys()[0]


@frappe.whitelist(methods=["POST"])
def subscribe(subscription, device=None, quiet=False):
	"""Turn notifications on for this device: the browser's push subscription, as it gives
	it (endpoint and keys). A device moves to whoever subscribes it last. Unless quiet (the
	app moving a subscription it had), the device is told notifications are on."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to turn notifications on."), frappe.PermissionError)
	subscription = frappe.parse_json(subscription)
	endpoint = subscription.get("endpoint")
	keys = subscription.get("keys") or {}
	if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
		frappe.throw(_("This device did not give a complete subscription."))

	values = {
		"user": frappe.session.user,
		"device": (device or "")[:140],
		"p256dh": keys["p256dh"],
		"auth": keys["auth"],
	}
	name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint})
	if name:
		frappe.db.set_value("Push Subscription", name, values)
	else:
		frappe.get_doc({"doctype": "Push Subscription", "endpoint": endpoint, **values}).insert(ignore_permissions=True)

	if frappe.utils.cint(quiet):
		return True
	frappe.enqueue(
		send_to_user,
		queue="short",
		enqueue_after_commit=True,
		user=frappe.session.user,
		title=_("Notifications are on"),
		body=_("You will be notified here of your requests, approvals and announcements."),
		url="/hrms/notifications",
		endpoint=endpoint,
	)
	return True


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
	frappe.db.delete("Push Subscription", {"endpoint": endpoint, "user": frappe.session.user})
	return True


@frappe.whitelist(methods=["GET"])
def mark_received(endpoint):
	"""Called by the app's service worker when a push reached the device, so the site
	knows its pushes arrive (Push Subscription > Last Received). A GET, as the worker has
	no CSRF token; it only stamps the device's own subscription, so it commits itself."""
	name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint, "user": frappe.session.user})
	if name:
		frappe.db.set_value("Push Subscription", name, "last_received", now_datetime(), update_modified=False)
		frappe.db.commit()
	return bool(name)


@frappe.whitelist(methods=["POST"])
def log_client_error(error):
	"""Why turning notifications on, or moving them, failed on a device (sent by the app)."""
	if frappe.session.user == "Guest":
		return
	frappe.log_error("Push notifications failed on a device", f"{frappe.session.user}\n{str(error)[:2000]}")


@frappe.whitelist()
def is_subscribed(endpoint):
	return bool(frappe.db.exists("Push Subscription", {"endpoint": endpoint, "user": frappe.session.user}))


# Sending


def on_notification(doc, method=None):
	"""PWA Notification after insert: push it to its user's devices, after the commit."""
	if not doc.to_user or not frappe.db.exists("Push Subscription", {"user": doc.to_user}):
		return
	frappe.enqueue(
		send_notification, queue="short", enqueue_after_commit=True, notification=doc.name
	)


def send_notification(notification):
	doc = frappe.get_doc("PWA Notification", notification)
	send_to_user(
		doc.to_user,
		title=get_title(doc),
		body=_as_text(doc.message),
		url=get_route(doc.reference_document_type, doc.reference_document_name),
		tag=doc.name,
	)


def _as_text(message):
	"""The notification's text without its markup, its line breaks kept."""
	text = re.sub(r"<br\s*/?>", "\n", message or "", flags=re.I)
	return strip_html(text).strip()


def get_title(doc):
	"""The push's title, in its user's language: what it is about."""
	lang = frappe.db.get_value("User", doc.to_user, "language") or frappe.db.get_default("lang")
	if doc.reference_document_type == "HR Announcement":
		# Not "Announcement": Chrome on Android hides notifications titled so (in Arabic, the
		# word for an advert) as possible spam.
		return frappe.db.get_value("HR Announcement", doc.reference_document_name, "title") or _("From HR", lang=lang)
	titles = {
		"Shift Type": "Attendance Watch",
		"Employee Checkin": "Check-in reminder",
		"Holiday List": "Holiday",
		"Employee": "Occasion",
	}
	label = titles.get(doc.reference_document_type) or doc.reference_document_type
	return _(label, lang=lang) if label else get_app_title()


def get_route(doctype, name):
	route = ROUTES.get(doctype)
	path = route.format(name=name) if route and name else route or "notifications"
	return f"/hrms/{path}"


def get_app_title():
	return frappe.db.get_single_value("Website Settings", "app_name") or "Frappe HR"


def send_to_user(user, title, body, url=None, tag=None, endpoint=None):
	"""Push to every device of the user (or one of them); devices the push service no
	longer knows are dropped."""
	from pywebpush import WebPushException, webpush
	from py_vapid import Vapid

	filters = {"user": user}
	if endpoint:
		filters["endpoint"] = endpoint
	devices = frappe.get_all("Push Subscription", filters=filters, fields=["name", "endpoint", "p256dh", "auth"])
	if not devices:
		return 0

	vapid = Vapid.from_pem(get_keys()[1].encode())
	claims = {"sub": f"mailto:{_contact()}"}
	payload = json.dumps(
		{
			"title": title or get_app_title(),
			"body": body or "",
			"url": url or "/hrms/notifications",
			"tag": tag,
			# No icon or badge: Chrome on Android hides notifications with them as possible
			# spam, and shows the site's own icon without them.
		},
		ensure_ascii=False,
	)

	sent = 0
	for device in devices:
		try:
			webpush(
				subscription_info={"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}},
				data=payload,
				vapid_private_key=vapid,
				vapid_claims=dict(claims),
				# Delivered at once even when the phone is idle: these are notifications
				# the user is meant to see (Android delays normal ones in battery saving).
				headers={"Urgency": "high"},
				ttl=TTL_SECONDS,
				timeout=10,
			)
			frappe.db.set_value("Push Subscription", device.name, "last_sent", now_datetime(), update_modified=False)
			sent += 1
		except WebPushException as error:
			status = getattr(error.response, "status_code", None)
			if status in (404, 410):
				frappe.db.delete("Push Subscription", device.name)
			else:
				frappe.log_error(f"Push to {user} failed", f"{error}\n{getattr(error.response, 'text', '')}")
		except Exception:
			frappe.log_error(f"Push to {user} failed")
	return sent


def _contact():
	"""Who the push services may contact about this site's pushes, as a full address (they
	refuse others): the outgoing email account, or the first System Manager's email."""
	import re

	valid = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
	email = frappe.db.get_value("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "email_id")
	if email and valid.match(email):
		return email
	managers = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User", "parent": ("not in", ("Administrator", "Guest"))}, pluck="parent"
	)
	for user in frappe.get_all("User", filters={"name": ("in", managers or [""]), "enabled": 1}, fields=["email"], order_by="creation asc"):
		if user.email and valid.match(user.email):
			return user.email
	host = frappe.utils.get_host_name()
	return f"push@{host}" if "." in host else "push@example.com"
