#!/usr/bin/env python
# coding: utf8
"""
image processing with PIL's ease and skimage's power

:requires:
* `scikit-image <http://scikit-image.org/>`_
* `PIL or Pillow <http://pypi.python.org/pypi/pillow/>`_

:optional:
* `pdfminer.six <http://pypi.python.org/pypi/pdfminer.six/>`_ for pdf input

"""
from __future__ import division #"true division" everywhere

__author__ = "Philippe Guglielmetti"
__copyright__ = "Copyright 2015, Philippe Guglielmetti"
__credits__ = ['Brad Montgomery http://bradmontgomery.net']
__license__ = "LGPL"

# http://python-prepa.github.io/ateliers/image_tuto.html

import numpy as np
import skimage

# import PIL.Image as PILImage

import six
from six.moves.urllib_parse import urlparse
from six.moves.urllib import request
urlopen = request.urlopen

import os, sys, math, base64, functools, logging

from . import math2, itertools2
from .drawing import Drawing #to read vector pdf files as images
from .colors import Color
from .plot import Plot

class Mode(object):
    def __init__(self,name,nchannels,type,min, max):
        self.name=name.lower()
        self.nchannels=nchannels
        self.type=type
        self.min=min
        self.max=max

modes = {
    # http://pillow.readthedocs.io/en/3.1.x/handbook/concepts.html#concept-modes
    # + some others
    '1'     : Mode('bool',1,np.uint8,0,1), # binary
    'F'     : Mode('gray',1,np.float,0,1), # gray level
    'U'     : Mode('gray',1,np.uint16,0,65535), # skimage gray level
    'I'     : Mode('gray',1,np.int16,-32768,32767), # skimage gray level
    'L'     : Mode('gray',1,np.uint8,0,255), # single layer or RGB(A)
    'P'     : Mode('gray',1,np.uint8,0,255), # indexed color (palette)
    'RGB'   : Mode('rgb',3,np.uint8,0,255),
    'RGBA'  : Mode('rgba',4,np.uint8,0,255),
    'CMYK'  : Mode('cmyk',4,np.uint8,0,255),
    'LAB'   : Mode('lab',3,np.float,-100,100),
    'XYZ'   : Mode('xyz',3,np.float,0,1), # https://en.wikipedia.org/wiki/CIE_1931_color_space
    'HSV'   : Mode('hsv',3,np.float,0,1), # https://en.wikipedia.org/wiki/HSL_and_HSV
}



from PIL.Image import NEAREST, BILINEAR, BICUBIC, ANTIALIAS

# skimage equivalents of PIL filters
# see http://www2.fhstp.ac.at/~webmaster/Imaging-1.1.5/PIL/ImageFilter.py
from PIL.ImageFilter import BLUR, CONTOUR, DETAIL, EDGE_ENHANCE, EDGE_ENHANCE_MORE, EMBOSS, FIND_EDGES, SMOOTH, SMOOTH_MORE, SHARPEN

#PIL+SKIMAGE dithering methods

from PIL.Image import NEAREST, ORDERED, RASTERIZE, FLOYDSTEINBERG
PHILIPS=FLOYDSTEINBERG+1
SIERRA=FLOYDSTEINBERG+2
STUCKI=FLOYDSTEINBERG+3
RANDOM=FLOYDSTEINBERG+10

dithering={
    NEAREST : 'nearest',
    ORDERED : 'ordered', # Not yet implemented in Pillow
    RASTERIZE : 'rasterize', # Not yet implemented in Pillow
    FLOYDSTEINBERG : 'floyd-steinberg',
    PHILIPS: 'philips', #http://www.google.com/patents/WO2002039381A2
    SIERRA: 'sierra filter lite',
    STUCKI: 'stucki',
    RANDOM: 'random',
}

def adapt_rgb(func):
    """Decorator that adapts to RGB(A) images to a gray-scale filter.
    :param apply_to_rgb: function
        Function that returns a filtered image from an image-filter and RGB
        image. This will only be called if the image is RGB-like.
    """
    # adapted from https://github.com/scikit-image/scikit-image/blob/master/skimage/color/adapt_rgb.py
    @functools.wraps(func)
    def image_filter_adapted(image, *args, **kwargs):
        channels=list(image.split())
        if len(channels)>1:
            for i in range(3): #RGB. If there is an A, it is untouched
                channels[i]=(func)(channels[i], *args, **kwargs)
            return Image(channels,image.mode)
        else:
            return func(image, *args, **kwargs)
    return image_filter_adapted

class Image(Plot):
    def __init__(self, data=None, mode=None, **kwargs):
        """
        :param data: can be either:
        * `PIL.Image` : makes a copy
        * string : path of image to load
        * None : creates an empty image with kwargs parameters:
        ** size : (y,x) pixel size tuple
        ** mode : 'L' (gray) by default
        ** color: to fill None=black by default
        """
        if data is None:
            self.mode = mode = mode or 'L'
            n=modes[mode].nchannels
            size = tuple(kwargs.get('size',(0,0)))
            if n>1 : size=size+ (n,)
            color=Color(kwargs.get('color','black')).rgb
            if n==1:
                color=color[0] #somewhat brute
            self.array = np.ones(size, dtype=modes[mode].type) * color
        elif isinstance(data,Image): #copy constructor
            self.mode=data.mode
            self.array=data.array
        elif isinstance(data,six.string_types): #assume a path
            self.open(data,**kwargs)
        else: # assume some kind of array
            dtype=modes[mode].type if mode else None
            try:
                self.array=np.asarray(data,dtype)
            except: # assume data is a list of image planes to merge
                data=np.concatenate([x.array[..., np.newaxis] for x in data], axis=-1)
                self.array=np.asarray(data,dtype)
            self.mode=mode or self.guessmode()

    @property
    def shape(self):
        return self.array.shape

    @property
    def size(self):
        return self.shape[:2]

    @property
    def nchannels(self):
        return 1 if len(self.shape)==2 else self.shape[-1]

    @property
    def npixels(self):
        return math2.mul(self.size)


    def __nonzero__(self):
        return self.npixels >0

    def __lt__(self, other):
        """ is smaller"""
        return  self.npixels < other.pixels

    def guessmode(self):
        n=self.nchannels
        if n>1:
            return 'RGBA'[:n]
        if np.issubdtype(self.array.dtype,float):
            return 'F'
        if self.array.dtype == np.uint8:
            return 'L'
        return 'I'

    def open(self,path):
        from skimage import io
        if not io.util.is_url(path):
            path = os.path.abspath(path)
        self._path = path
        ext=path[-3:].lower()
        if ext=='pdf':
            self.array=read_pdf(path)
        else:
            with io.util.file_or_url_context(path) as context:
                self.array = io.imread(context)
        self.mode=self.guessmode()
        return self

    def save(self,path,**kwargs):
        try:
            f=255/modes[self.mode].max
            a=np.asarray(self.array*f,np.uint8)
            skimage.io.imsave(path,a,**kwargs)
            return self
        except IOError as e:
            pass
        try:
            im=self.convert('RGBA')
        except IOError:
            im=self.convert('L') #gray

        return im.save(path,**kwargs)

    def _repr_svg_(self, **kwargs):
        raise NotImplementedError() #and should never be ...
        #... it causes _repr_png_ to be called by Plot._repr_html_

    def render(self, fmt='png'):
        import PIL.Image
        buffer = six.BytesIO()
        PIL.Image.fromarray(self.array).save(buffer, fmt)
        return buffer.getvalue()

    # methods for PIL.Image compatibility (see http://effbot.org/imagingbook/image.htm )
    def getdata(self):
        return self.array

    def split(self, mode=None):
        if mode and mode != self.mode:
            im=self.convert(mode)
        else:
            im=self
        if self.nchannels==1:
            return [self] #for coherency

        mode='L'
        return [Image(self._get_channel(i),mode) for i in range(self.nchannels)]

    def getpixel(self,yx):
        if self.nchannels==1:
            return self.array[yx[0],yx[1]]
        else:
            return self.array[yx[0],yx[1],:]

    def crop(self,lurl):
        """
        :param lurl: 4-tuple with left,up,right,bottom int coordinates
        :return: Image
        """
        if self.nchannels==1:
            a=self.array[lurl[1]:lurl[3],lurl[0]:lurl[2]]
        else:
            a=self.array[lurl[1]:lurl[3],lurl[0]:lurl[2],:]
        return Image(a,self.mode)

    def __getitem__(self,slice):
        try:
            return self.getpixel(slice)
        except TypeError:
            pass
        left, upper, right, lower=slice[1].start,slice[0].start,slice[1].stop,slice[0].stop
        # calculate box module size so we handle negative coords like in slices
        w,h = self.size
        upper = upper%h if upper else 0
        lower = lower%h if lower else h
        left = left%w if left else 0
        right = right%w if right else w

        return self.crop((left, upper, right, lower))

    def resize(self,size, filter=None, **kwargs):
        """
        :return: a resized copy of an image.
        :param size: int tuple (width, height) requested size in pixels
        :param filter:
            * NEAREST (use nearest neighbour),
            * BILINEAR (linear interpolation in a 2x2 environment),
            * BICUBIC (cubic spline interpolation in a 4x4 environment)
            * ANTIALIAS (a high-quality downsampling filter)
        :param kwargs: axtra parameters passed to skimage.transform.resize
        """
        from skimage.transform import resize
        order=0 if filter in (None,NEAREST) else 1 if filter==BILINEAR else 3
        order=kwargs.pop('order',order)
        array=resize(self.array, size, order, preserve_range=True, **kwargs)
        return Image(array, self.mode)

    def paste(self,image,box, mask=None):
        """Pastes another image into this image.

        :param image:   image to paste, or color given as a single numerical value for single-band images, and a tuple for multi-band images.
        :param box: 2-tuple giving the upper left corner
                    or 4-tuple defining the left, upper, right, and lower pixel coordinate,
                    or None (same as (0, 0)).
                    If a 4-tuple is given, the size of the pasted image must match the size of the region.
        :param mask:optional image to update only the regions indicated by the mask.
                    You can use either “1”, “L” or “RGBA” images (in the latter case, the alpha band is used as mask).
                    Where the mask is 255, the given image is copied as is.
                    Where the mask is 0, the current value is preserved.
                    Intermediate values can be used for transparency effects.
                    Note that if you paste an “RGBA” image, the alpha band is ignored.
                    You can work around this by using the same image as both source image and mask.
        """
        if len(box)==2:
            box=(box[0],box[1])

    def threshold(self, level=None):
        from skimage.filters import threshold_otsu
        if level is None :
            level=threshold_otsu(self.array)
        return Image(self.array>level, '1')

    def quantize(self, levels):
        a=quantize(self.array,levels)
        return Image(a,'P')


    def convert(self,mode,**kwargs):
        a=convert(self.array,self.mode,mode)
        return Image(a, mode)


    def _get_channel(self, channel):
        """Return a specific dimension out of the raw image data slice."""
        # https://github.com/scikit-image/scikit-image/blob/master/skimage/novice/_novice.py
        a=self.array[:, :, channel]
        return a

    def _set_channel(self, channel, value):
        """Set a specific dimension in the raw image data slice."""
        # https://github.com/scikit-image/scikit-image/blob/master/skimage/novice/_novice.py
        self.array[:, :, channel] = value

    # representations, data extraction and conversions

    def __repr__(self):
        size=getattr(self,'size','unknown')
        return "%s(mode=%s size=%s)" % (
            self.__class__.__name__,self.mode, size,
            )

    def ndarray(self):
        """ http://docs.scipy.org/doc/numpy-1.10.0/reference/generated/numpy.ndarray.html

        :return: `numpy.ndarray` of image
        """
        data = list(self.getdata())
        w,h = self.size
        A = np.zeros((w*h), 'd')
        i=0
        for val in data:
            A[i] = val
            i=i+1
        A=A.reshape(w,h)
        return A


    # hash and distance

    def average_hash(self, hash_size=8):
        """
        Average Hash computation
        Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html

        :param hash_size: int sqrt of the hash size. 8 (64 bits) is perfect for usual photos
        :return: list of hash_size*hash_size bool (=bits)
        """
        # https://github.com/JohannesBuchner/imagehash/blob/master/imagehash/__init__.py
        if self.nchannels>1:
            image = self.grayscale()
        else:
            image=self

        image = image.resize((hash_size, hash_size), ANTIALIAS)
        pixels = image.array.reshape((1,hash_size*hash_size))[0]
        avg = pixels.mean()
        diff=pixels > avg
        return math2.num_from_digits(diff,2)

    def dist(self,other, hash_size=8):
        """ distance between images

        :param hash_size: int sqrt of the hash size. 8 (64 bits) is perfect for usual photos
        :return: float
            =0 if images are equal or very similar (same average_hash)
            =1 if images are completely decorrelated (half of the hash bits are the same by luck)
            =2 if images are inverted
        """
        h1=self.average_hash(hash_size)
        h2=other.average_hash(hash_size)
        if h1==h2:
            return 0
        # http://stackoverflow.com/questions/9829578/fast-way-of-counting-non-zero-bits-in-python
        diff=bin(h1^h2).count("1") # ^is XOR
        diff=2*diff/(hash_size*hash_size)
        return diff

    def __hash__(self):
        return self.average_hash(8)

    def __abs__(self):
        """:return: float Frobenius norm of image"""
        return np.linalg.norm(self.array)

    def invert(self):
        return Image(modes[self.mode].max-self.array,self.mode)

    __neg__=__inv__=invert #aliases

    def grayscale(self):
        return self.convert('F')

    def colorize(self,color0,color1=None):
        """colorize a grayscale image

        :param color0,color1: 2 colors.
            - If only one is specified, image is colorized from white (for 0) to the specified color (for 1)
            - if 2 colors are specified, image is colorized from color0 (for 0) to color1 (for 1)
        :return: RGB(A) color
        """
        if color1 is None:
            color1=color0
            color0='white'
        color0=Color(color0).rgb
        color1=Color(color1).rgb
        a=bool2rgb(self.array,color0,color1)
        return Image(a,'RGB')

    @adapt_rgb
    def dither(self,method=FLOYDSTEINBERG):
        L=modes[self.mode].max
        a=dither(self.invert().array,method,L=L)
        return Image(a,'1')

    def normalize(self,newmax=255,newmin=0):
        #http://stackoverflow.com/questions/7422204/intensity-normalization-of-image-using-pythonpil-speed-issues
        #warning : this normalizes each channel independently, so we don't use @adapt_rgb here
        arr=_normalize(np.array(self),newmax,newmin)
        return Image(arr)

    @adapt_rgb
    def filter(self,f):
        #PIL filters
        if f==BLUR:
            CONTOUR, DETAIL, EDGE_ENHANCE, EDGE_ENHANCE_MORE, EMBOSS, FIND_EDGES, SMOOTH, SMOOTH_MORE, SHARPEN
        else: # scikit-image filter or similar ?
            return Image(f(self.array))


    def correlation(self, other):
        """Compute the correlation between two, single-channel, grayscale input images.
        The second image must be smaller than the first.
        :param other: the Image we're looking for
        """
        from scipy import signal
        input = self.ndarray()
        match = other.ndarray()
        c=signal.correlate2d(input,match)
        return Image(c)

    def scale(self,s):
        """resize image by factor s

        :param s: (sx, sy) tuple of float scaling factor, or scalar s=sx=sy
        :return: Image scaled
        """
        try:
            s[1]
        except:
            s=[s,s]
        w,h=self.size
        return self.resize((int(w*s[0]+0.5),int(h*s[1]+0.5)))

    @adapt_rgb
    def shift(self,dx,dy,**kwargs):
        from scipy.ndimage.interpolation import shift as shift2
        a=shift2(self.array,(dy,dx), **kwargs)
        return Image(a, self.mode)

    def expand(self,size,ox=None,oy=None):
        """
        :return: image in larger canvas size, pasted at ox,oy
        """
        im = Image(None, self.mode, size=size)
        (w,h)=self.size
        if w*h==0: #resize empty image...
            return im
        if ox is None: #center
            ox=(size[0]-w)//2
        elif ox<0: #from the right
            ox=size[0]-w+ox
        if oy is None: #center
            oy=(size[1]-h)//2
        elif oy<0: #from bottom
            oy=size[1]-h+oy
        if math2.is_integer(ox) and math2.is_integer(oy):
            im.paste(self, tuple(map(math2.rint,(ox,oy,ox+w,oy+h))))
        elif ox>=0 and oy>=0:
            im.paste(self, (0,0,w,h))
            im=im.shift(ox,oy)
        else:
            raise NotImplemented #TODO; something for negative offsets...
        return im

    #@adapt_rgb
    def compose(self,other,a=0.5,b=0.5):
        """compose new image from a*self + b*other
        """
        if self and other and self.mode != other.mode:
            pass # other=other.convert(self.mode)
        if self:
            d1=self.array # np.array(self,dtype=np.float)
        else:
            d1=None
        if other:
            d2=other.array # np.array(other,dtype=np.float)
        else:
            d2=None
        if d1 is not None:
            if d2 is not None:
                return Image(a*d1+b*d2)
            else:
                return Image(a*d1)
        else:
            return Image(b*d2)

    def add(self,other,pos=(0,0),alpha=1):
        """ simply adds other image at px,py (subbixel) coordinates
        :warning: result is normalized in case of overflow
        """
        #TOD: use http://stackoverflow.com/questions/9166400/convert-rgba-png-to-rgb-with-pil
        px,py=pos
        assert px>=0 and py>=0
        im1,im2=self,other
        size=(max(im1.size[0],int(im2.size[0]+px+0.999)),
              max(im1.size[1],int(im2.size[1]+py+0.999)))
        if not im1.mode: #empty image
            im1.mode=im2.mode
        im1=im1.expand(size,0,0)
        im2=im2.expand(size,px,py)
        return im1.compose(im2,1,alpha)

    def __add__(self,other):
        return self.compose(other,1,1)

    def __sub__(self,other):
        return self.compose(other,1,-1)

    def __mul__(self,other):
        if isinstance(other,six.string_types):
            return self.colorize(other)
        if math2.is_number(other):
            return self.compose(None,other)
        if other.nchannels>self.nchannels:
            return other*self
        if other.nchannels==1:
            if self.nchannels==1:
                return self.compose(None,np.array(other,dtype=np.float))
            rgba=list(self.split('RGBA'))
            rgba[-1]=rgba[-1]*other
            return Image(rgba,'RGBA')
        raise NotImplemented('%s * %s'%(self,other))


    def draw(self,entity):
        from . import drawing, geom
        try: #iterable ?
            for e in entity:
                draw(e)
            return
        except:
            pass

        if isinstance(entity,geom.Circle):
            box=entity.bbox()
            box=(box.xmin, box.ymin, box.xmax, box.ymax)
            ImageDraw.Draw(self).ellipse(box, fill=255)
        else:
            raise NotImplemented
        return self

def rgb2rgba(array):
    s=array.shape
    if s[2]==4: #already RGBA
        return array
    a=np.zeros(s[:2],s.dtype())
    return np.append(array,a,0)

#from http://stackoverflow.com/questions/9166400/convert-rgba-png-to-rgb-with-pil

def alpha_to_color(image, color=(255, 255, 255)):
    """Set all fully transparent pixels of an RGBA image to the specified color.
    This is a very simple solution that might leave over some ugly edges, due
    to semi-transparent areas. You should use alpha_composite_with color instead.

    Source: http://stackoverflow.com/a/9166671/284318

    Keyword Arguments:
    image -- PIL RGBA Image object
    color -- Tuple r, g, b (default 255, 255, 255)

    """
    x = np.array(image)
    r, g, b, a = np.rollaxis(x, axis=-1)
    r[a == 0] = color[0]
    g[a == 0] = color[1]
    b[a == 0] = color[2]
    x = np.dstack([r, g, b, a])
    return Image.fromarray(x, 'RGBA')


def alpha_composite(front, back):
    """Alpha composite two RGBA images.

    Source: http://stackoverflow.com/a/9166671/284318

    Keyword Arguments:
    front -- PIL RGBA Image object
    back -- PIL RGBA Image object

    The algorithm comes from http://en.wikipedia.org/wiki/Alpha_compositing

    """
    front = np.asarray(front)
    back = np.asarray(back)
    result = np.empty(front.shape, dtype=np.float)
    alpha = np.index_exp[:, :, 3:]
    rgb = np.index_exp[:, :, :3]
    falpha = front[alpha] / 255.0
    balpha = back[alpha] / 255.0
    result[alpha] = falpha + balpha * (1 - falpha)
    old_setting = np.seterr(invalid='ignore')
    result[rgb] = (front[rgb] * falpha + back[rgb] * balpha * (1 - falpha)) / result[alpha]
    np.seterr(**old_setting)
    result[alpha] *= 255
    np.clip(result, 0, 255)
    # astype('uint8') maps np.nan and np.inf to 0
    result = result.astype(np.uint8)
    result = Image.fromarray(result, 'RGBA')
    return result


def alpha_composite_with_color(image, color=(255, 255, 255)):
    """Alpha composite an RGBA image with a single color image of the
    specified color and the same size as the original image.

    Keyword Arguments:
    image -- PIL RGBA Image object
    color -- Tuple r, g, b (default 255, 255, 255)

    """
    back = Image.new('RGBA', size=image.size, color=color + (255,))
    return alpha_composite(image, back)


def pure_pil_alpha_to_color_v1(image, color=(255, 255, 255)):
    """Alpha composite an RGBA Image with a specified color.

    NOTE: This version is much slower than the
    alpha_composite_with_color solution. Use it only if
    numpy is not available.

    Source: http://stackoverflow.com/a/9168169/284318

    Keyword Arguments:
    image -- PIL RGBA Image object
    color -- Tuple r, g, b (default 255, 255, 255)

    """
    def blend_value(back, front, a):
        return (front * a + back * (255 - a)) / 255

    def blend_rgba(back, front):
        result = [blend_value(back[i], front[i], front[3]) for i in (0, 1, 2)]
        return tuple(result + [255])

    im = image.copy()  # don't edit the reference directly
    p = im.load()  # load pixel array
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            p[x, y] = blend_rgba(color + (255,), p[x, y])

    return im

def pure_pil_alpha_to_color_v2(image, color=(255, 255, 255)):
    """Alpha composite an RGBA Image with a specified color.

    Simpler, faster version than the solutions above.

    Source: http://stackoverflow.com/a/9459208/284318

    Keyword Arguments:
    image -- PIL RGBA Image object
    color -- Tuple r, g, b (default 255, 255, 255)

    """
    image.load()  # needed for split()
    background = Image.new('RGB', image.size, color)
    background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
    return background

def disk(radius,antialias=ANTIALIAS):
    from skimage.draw import circle, circle_perimeter_aa
    size = (2*radius+2, 2*radius+2)
    img = np.zeros(size, dtype=np.double)
    rr, cc = circle(radius+1,radius+1,radius)
    img[rr, cc] = 1

    rr, cc, val = circle_perimeter_aa(radius+1,radius+1,radius)
    img[rr, cc] = val
    return Image(img)

def fspecial(name,**kwargs):
    """mimics the Matlab image toolbox fspecial function
    http://www.mathworks.com/help/images/ref/fspecial.html?refresh=true
    """
    if name=='disk':
        return disk(kwargs.get('radius',5)) # 5 is default in Matlab
    raise NotImplemented

def _normalize(array,newmax=255,newmin=0):
    #http://stackoverflow.com/questions/7422204/intensity-normalization-of-image-using-pythonpil-speed-issues
    #warning : don't use @adapt_rgb here as it would normalize each channel independently
    t=array.dtype
    if len(array.shape)==2 : #single channel
        n=1
        minval = array.min()
        maxval = array.max()
        array += newmin-minval
        if maxval is not None and minval != maxval:
            array=array.astype(np.float)
            array *= newmax/(maxval-minval)
    else:
        n=min(array.shape[2],3) #if RGBA, ignore A channel
        minval = array[:,:,0:n].min()
        maxval = array[:,:,0:n].max()
        array=array.astype(np.float)
        for i in range(n):
            array[...,i] += newmin-minval
            if maxval is not None and minval != maxval:
                array[...,i] *= newmax/(maxval-minval)
    return array.astype(t)

def read_pdf(filename,**kwargs):
    """ reads a bitmap graphics on a .pdf file
    only the first page is parsed
    """
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFResourceManager
    from pdfminer.pdfinterp import PDFPageInterpreter
    from pdfminer.pdfdevice import PDFDevice
    # PDF's are fairly complex documents organized hierarchically
    # PDFMiner parses them using a stack and calls a "Device" to process entities
    # so here we define a Device that processes only "paths" one by one:


    class _Device(PDFDevice):
        def render_image(self, name, stream):
            try:
                self.im=PILImage.open(six.BytesIO(stream.rawdata))
            except Exception as e:
                logging.error(e)


    #then all we have to do is to launch PDFMiner's parser on the file
    fp = open(filename, 'rb')
    parser = PDFParser(fp)
    document = PDFDocument(parser, fallback=False)
    rsrcmgr = PDFResourceManager()
    device = _Device(rsrcmgr)
    device.im=None #in case we can't find an image in file
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for page in PDFPage.create_pages(document):
        interpreter.process_page(page)
        break #handle one page only

    im=device.im

    if im is None: #it's maybe a drawing
        fig=Drawing(filename).draw(**kwargs)
        im=fig2img(fig)

    return im

def fig2img ( fig ):
    """
    Convert a Matplotlib figure to a PIL Image in RGBA format and return it

    :param fig: matplotlib figure
    :return: PIL image
    """
    #http://www.icare.univ-lille1.fr/wiki/index.php/How_to_convert_a_matplotlib_figure_to_a_numpy_array_or_a_PIL_image

    fig.canvas.draw ( )

    # Get the RGBA buffer from the figure
    w,h = fig.canvas.get_width_height()
    buf = np.fromstring ( fig.canvas.tostring_argb(), dtype=np.uint8 )
    buf.shape = ( w, h,4 )

    # canvas.tostring_argb give pixmap in ARGB mode. Roll the ALPHA channel to have it in RGBA mode
    buf = np.roll ( buf, 3, axis = 2 )
    w, h, _ = buf.shape
    return PILImage.frombytes( "RGBA", ( w ,h ), buf.tostring( ) )

# from https://github.com/scikit-image/skimage-demos/blob/master/dither.py
# see https://bitbucket.org/kuraiev/halftones for more

def quantize(image, N=2, L=1):
    """Quantize a gray image.
    :param image: ndarray input image.
    :param N: int number of quantization levels.
    :param L: float max value.
    """
    T = np.linspace(0, L, N, endpoint=False)[1:]
    return np.digitize(image.flat, T).reshape(image.shape)



def dither(image, method=FLOYDSTEINBERG, N=2, L=1):
    """Quantize a gray image, using dithering.
    :param image: ndarray input image.
    :param method: enum
    :param N: int number of quantization levels.
    References
    ----------
    http://www.efg2.com/Lab/Library/ImageProcessing/DHALF.TXT
    """
    if method==NEAREST:
        return quantize(image,N,L)
    elif method==RANDOM:
        img_dither_random = image + np.abs(np.random.normal(size=image.shape,scale=1./(3 * N)))
        return quantize(img_dither_random, N,L)

    image = image.copy()

    if method == PHILIPS:
        positions = [(0,0)]
        weights = [1]
    elif method==SIERRA:
        positions = [(0, 1), (1, -1), (1, 0)]
        weights = [2, 1, 1]
    elif method==STUCKI:
        positions = [(0, 1), (0, 2), (1, -2), (1, -1),
               (1, 0), (1, 1), (1, 2),
               (2, -2), (2, -1), (2, 0), (2, 1), (2, 2)]
        weights = [         8, 4,
                   2, 4, 8, 4, 2,
                   1, 2, 4, 2, 1]
    else:
        if method!=FLOYDSTEINBERG:
            logging.warning('dithering method %s not yet implemented. fallback to Floyd-Steinberg'%method)
        positions = [(0, 1), (1, -1), (1, 0), (1, 1)]
        weights = [7, 3, 5, 1]

    weights = weights / np.sum(weights)

    T = np.linspace(0, L, N, endpoint=False)[1:]
    rows, cols = image.shape

    out = np.zeros_like(image, dtype=float)
    for i in range(rows):
        for j in range(cols):
            # Quantize
            out[i, j], = np.digitize([image[i, j]], T)

            # Propagate quantization noise
            d = (image[i, j] - out[i, j] / (N - 1))
            for (ii, jj), w in zip(positions, weights):
                ii = i + ii
                jj = j + jj
                if ii < rows and jj < cols:
                    image[ii, jj] += d * w

    return out

gray2bool=dither

def rgb2cmyk(rgb):
    from skimage.color.colorconv import _prepare_colorarray
    arr = _prepare_colorarray(rgb)

    cmy=1-arr

    k = np.amin(cmy,axis=2)
    w = 1-k
    c = (cmy[:,:,0] - k) / w
    m = (cmy[:,:,1] - k) / w
    y = (cmy[:,:,2] - k) / w

    return np.concatenate([x[..., np.newaxis] for x in [c,m,y,k]], axis=-1)

def bool2rgb(im,color0=(0,0,0), color1=(1,1,1)):
    color0=np.asarray(color0,np.float)
    color1=np.asarray(color1,np.float)
    d=color1-color0
    return np.outer(im,d)+color0

#build a graph of available converters
#as in https://github.com/gtaylor/python-colormath

from .graph import DiGraph
import skimage.color as skcolor
converters=DiGraph(multi=False) # a nx.DiGraph() would suffice, but my DiGraph are better
for source in modes:
    for target in modes:
        key=(modes[source].name, modes[target].name)
        if key[0]==key[1]:
            continue
        else:
            convname='%s2%s'%key
            converter = getattr(sys.modules[__name__], convname,None)
            if converter is None:
                converter=getattr(skcolor, convname,None)
                
        if converter:
            converters.add_edge(key[0],key[1],{'f':converter})

def convert(im,source,target,**kwargs):
    """convert an image between modes, eventually using intermediary steps
    :param im: nparray (x,y,n) containing image
    :param source: string : key of source image mode in modes
    :param target: string : key of target image mode in modes
    """
    source,target=modes[source.upper()].name,modes[target.upper()].name
    if source==target: return im
    path=converters.shortest_path(source, target)
    for u,v in itertools2.pairwise(path):
        im=converters[u][v][0]['f'](im,**kwargs)
    return im #isn't it beautiful ?


    a=np.copy(self.array) #because we'll change the type in place below
    #then change array type if required
    dtype=modes[mode].type
    if a.dtype==dtype:
        pass
    elif dtype==np.float:
        a=skimage.img_as_float(a)
    elif dtype==np.int16:
        a=skimage.img_as_int(a)
    elif dtype==np.uint16:
        a=skimage.img_as_uint(a)
    elif dtype==np.uint8:
        a=skimage.img_as_ubyte(a)
    else:
        pass #keep the wrong type for now and see what happens

