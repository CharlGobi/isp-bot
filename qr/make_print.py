"""Build an A4 printable poster (PDF + PNG) around the donation QR code."""
import sys
from PIL import Image, ImageDraw, ImageFont

qr_path, out_base = sys.argv[1], sys.argv[2]
W, H = 2480, 3508  # A4 at 300 dpi
PINK = "#E6007E"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font = lambda p, n: ImageFont.truetype(p, n)

page = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(page)
d.rectangle([0, 0, W, 420], fill=PINK)
d.text((W / 2, 210), "I LOVE ♥ BOOBIES", fill="white", font=font(BOLD, 150), anchor="mm")
d.text((W / 2, 640), "Scan to donate", fill="black", font=font(BOLD, 190), anchor="mm")
d.text((W / 2, 820), "Choose your amount. Every rand counts.", fill="#333333", font=font(REG, 90), anchor="mm")

qr = Image.open(qr_path).convert("RGB").resize((1800, 1800), Image.NEAREST)
page.paste(qr, ((W - 1800) // 2, 960))

d.text((W / 2, 2880), "Point your phone camera at the code.", fill="#333333", font=font(REG, 80), anchor="mm")
d.text((W / 2, 3020), "iloveboobies.co.za", fill=PINK, font=font(BOLD, 110), anchor="mm")
d.rectangle([0, H - 120, W, H], fill=PINK)

page.save(out_base + ".png", dpi=(300, 300))
page.save(out_base + ".pdf", resolution=300)
