import sys, base64, io
from PIL import Image
png=sys.argv[1]; out_webp=sys.argv[2] if len(sys.argv)>2 else None
MAXW=760; Q=30
im=Image.open(png).convert("RGB")
if im.width>MAXW:
    h=int(im.height*MAXW/im.width)
    im=im.resize((MAXW,h))
buf=io.BytesIO()
im.save(buf,format="WEBP",quality=Q)
data=buf.getvalue()
if out_webp:
    open(out_webp,"wb").write(data)
print(base64.b64encode(data).decode())
