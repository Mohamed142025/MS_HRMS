"""The employee PWA's home screen icons and iOS launch screens, made from the two source
images in frontend/public:

- app-icon.png (square): the icons for Android (plain and maskable), iOS and the browser.
- splash screen.jpg (portrait): a launch screen for each iOS screen size that index.html
  lists, the picture fitted on its own background colour. Android draws its launch screen
  itself from the manifest (the icon on a background colour; see ms_hrms/pwa.py).

The results go to ms_hrms/public/pwa/ and are committed. Run again after changing either
source image, with the bench's Python (it has Pillow):

    cd apps/ms_hrms/frontend && ../../../env/bin/python scripts/make_pwa_images.py
"""

import re
from pathlib import Path

from PIL import Image, ImageStat

FRONTEND = Path(__file__).resolve().parent.parent
ICON = FRONTEND / "public" / "app-icon.png"
SPLASH = FRONTEND / "public" / "splash screen.jpg"
INDEX = FRONTEND / "index.html"
OUT = FRONTEND.parent / "ms_hrms" / "public" / "pwa"


def icon_background(icon):
	# The icon's own colour, just inside its rounded corner.
	return icon.convert("RGB").getpixel((icon.width // 2, icon.height // 12))


def corner_colour(picture, patch=24):
	"""The picture's background: the average of its four corners, as JPEG noise makes any
	single pixel slightly off."""
	means = [
		ImageStat.Stat(picture.crop((x, y, x + patch, y + patch))).mean
		for x in (0, picture.width - patch)
		for y in (0, picture.height - patch)
	]
	return tuple(round(sum(m[i] for m in means) / len(means)) for i in range(3))


def flattened(icon, size, background):
	"""The icon filled to the square: iOS and maskable icons may not be transparent."""
	square = Image.new("RGB", icon.size, background)
	square.paste(icon, mask=icon.split()[3])
	return square.resize((size, size), Image.LANCZOS)


def launch_screen(picture, width, height, background):
	"""The picture as large as it fits, centred on its background colour."""
	scale = min(width / picture.width, height / picture.height)
	fitted = picture.resize((round(picture.width * scale), round(picture.height * scale)), Image.LANCZOS)
	screen = Image.new("RGB", (width, height), background)
	screen.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
	return screen


def main():
	OUT.mkdir(parents=True, exist_ok=True)

	icon = Image.open(ICON).convert("RGBA")
	background = icon_background(icon)
	for size in (192, 512):
		icon.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png", optimize=True)
	flattened(icon, 512, background).save(OUT / "icon-maskable-512.png", optimize=True)
	flattened(icon, 180, background).save(OUT / "apple-touch-icon.png", optimize=True)
	icon.resize((196, 196), Image.LANCZOS).save(OUT / "favicon-196.png", optimize=True)

	picture = Image.open(SPLASH).convert("RGB")
	splash_background = corner_colour(picture)
	sizes = sorted({tuple(map(int, m)) for m in re.findall(r"/pwa/splash-(\d+)-(\d+)\.jpg", INDEX.read_text())})
	for width, height in sizes:
		launch_screen(picture, width, height, splash_background).save(
			OUT / f"splash-{width}-{height}.jpg", quality=82, optimize=True, progressive=True
		)

	print(f"icons from {ICON.name} (background #{'%02X%02X%02X' % background}), "
		f"{len(sizes)} launch screens from {SPLASH.name} (background #{'%02X%02X%02X' % splash_background})")


if __name__ == "__main__":
	main()
