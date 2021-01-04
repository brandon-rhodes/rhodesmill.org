# -*- coding: utf-8 -*-
"""Correct a standard LOTR map to be ready to project on Google Earth.
"""
import os
from math import cos, radians
from PIL import Image, ImageDraw, ImageFont

im = Image.open("maps-middle-earth-01.jpg")
xsize, ysize = im.size

# Some basic coordinates off of the image.

xRivendell = 425                # x of Rivendell
xHobbiton = 220                 # x of Hobbiton
yHobbiton = 277                 # y of Hobbiton
dHobbiton = 51. + 45./60.       # Oxford latitude: 51°45'N
Hobbiton_Rivendell_miles = 450. # approximate; will do more research
miles_per_degree = 69.2         # per degree of latitude

# Figure out some derived values from the above constants.

miles_per_pixel = Hobbiton_Rivendell_miles / (xRivendell - xHobbiton)
degrees_per_pixel = miles_per_pixel / miles_per_degree

def latitude(y):
    return radians(dHobbiton + (yHobbiton - y) * degrees_per_pixel)

# Find the location of the FreeSans font by asking the "locate" command,
# rather than hard-coding its location in a string constant.

font_path = os.popen('locate -n1 /FreeSans.ttf').read().strip()

# Draw red lines of latitude at five-degree increments, labeled in blue
# in a simple sans-serif font, to make it easy to place the image
# correctly on the globe displayed by Google Earth.

font = ImageFont.truetype(font_path, 24)
draw = ImageDraw.Draw(im)
for lat in range(30, 61, 5):
    y = yHobbiton + (dHobbiton - lat) / degrees_per_pixel
    draw.line((0, y, xsize, y), fill=(255,0,0))
    draw.text((xsize - 50, y), u'%sN' % lat, font=font, fill=(0,0,255))
del draw

# How much do we have to expand each row of the image horizontally?

def mag(y):
    return 1. / cos(latitude(y))

# How big will the whole image be?  The top row, at y=0, will be widest.

xfinal = int(xsize * mag(0))

# Build the mesh that stretches each line of pixels in the original
# image into a wider line of pixels in the resulting image.

xleft = xRivendell
xright = xsize - xRivendell
xoffset = xleft * mag(0) # x-coordinate on which to center the magnification
data = []
for y in range(0, ysize):
    m = mag(y)
    source_quad = (0, y-0.5, 0, y+0.5,
                   xsize, y+0.5, xsize, y-0.5) # the whole row of pixels
    dest_bbox = (int(xoffset - m * xleft), y,
                 int(xoffset + m * xright), y + 1) # a wider row
    data.append((dest_bbox, source_quad))

# Do the transform and save the result.

im = im.transform((xfinal, ysize), Image.MESH, data, Image.BICUBIC)
im.save("out.jpg")
