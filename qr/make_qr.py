import sys, qrcode
from PIL import Image, ImageDraw, ImageFont
URL="https://www.iloveboobies.co.za/products/donation-choose-your-amount"
out=sys.argv[1]; logo=sys.argv[2] if len(sys.argv)>2 else None
qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,box_size=int(__import__("os").environ.get("QR_BOX","20")),border=4)
qr.add_data(URL); qr.make(fit=True)
img=qr.make_image(fill_color="#000000",back_color="white").convert("RGB")
W=img.size[0]; s=int(W*0.26); x=(W-s)//2
d=ImageDraw.Draw(img)
d.rounded_rectangle([x-12,x-12,x+s+12,x+s+12],radius=30,fill="white")
if logo:
    L=Image.open(logo).convert("RGBA"); L.thumbnail((s,s))
    img.paste(L,((W-L.width)//2,(W-L.height)//2),L)
else:
    d.rounded_rectangle([x,x,x+s,x+s],radius=24,fill="#E6007E")
    f=lambda n:ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",n)
    for t,y,n in [("I LOVE",0.30,52),("♥",0.52,70),("BOOBIES",0.76,52)]:
        d.text((W/2,x+s*y),t,fill="white",font=f(int(n*W/1140)),anchor="mm")
img.save(out)
