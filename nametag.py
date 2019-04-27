from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import qrcode
import random

WIDTH = 640
HEIGHT = 480

def make_image(name, qr_hash):
    image = Image.new('RGB', (WIDTH, HEIGHT))
    name_arr = name.split(" ", 1)
    pixels = image.load()

    for k in range(0, WIDTH):
        for j in range(0, HEIGHT):
            if j <= HEIGHT/4:
                pixels[k, j] = (0, 47, 108)
            else:
                pixels[k, j] = (255, 255, 255)

    img2 = Image.open("static/nametag/heading.png")
    area = (20, 0)
    image.paste(img2, area)

    qr = qrcode.QRCode(
        version=1,
        box_size=11,
        border=1,
    )

    qr.add_data(qr_hash)
    qr_img =  qr.make_image()
    area = (0, 125)
    image.paste(qr_img, area)

    draw = ImageDraw.Draw(image)
    nameFont = ImageFont.truetype("static/nametag/Helvetica.ttf", 72)
    draw.text((340, 140), name_arr[0], (0,0,0), font=nameFont)
    draw.text((340, 210), name_arr[1], (0,0,0), font=nameFont)

    foodFont = ImageFont.truetype("static/nametag/Helvetica.ttf", 24)
    if random.random() > 0.5:
        draw.text((340, 320),"Food Wave:\t\t A",(0,0,0),font=foodFont)
    else:
        draw.text((340, 320),"Food Wave:\t\t B",(0,0,0),font=foodFont)
    filename = 'nametags/' + name  + '.png'
    image.save(filename)
