import OpenEXR, Imath
from PIL import Image, ImageChops

t0 = 'test/test_chunk_00000.exr'
t1 = 'test/test_chunk_00001.exr'

############################
def open_exr_as_rgbf_images( exr_file ):
    file = OpenEXR.InputFile( exr_file )
    pt = Imath.PixelType( Imath.PixelType.FLOAT )
    dw = file.header()['dataWindow']
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)

    rgbf = [Image.fromstring("F", size, file.channel(c, pt)) for c in "RGB"]

    return rgbf

############################
def convert_rgbf_images_to_rgb8_image( rgbf, lighest, darkest ):    
    scale = 255 / (lighest - darkest)
    
    def normalize_0_255( val ):
        return (v * scale) + darkest
    
    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]
    
    img = Image.merge("RGB", rgb8)
    
    return img

############################
def get_single_rgbf_extrema( rgbf ):
    extrema = [im.getextrema() for im in rgbf]
    darkest = min([lo for (lo,hi) in extrema])
    lighest = max([hi for (lo,hi) in extrema])

    return darkest, lighest

############################
def get_list_rgbf_extrema( rgbf_list ):
    assert len( rgbf_list ) > 0

    darkest, lighest = get_single_rgbf_extrema( rgbf_list[ 0 ] )
    
    for i in range( 1, len( rgbf_list ) ):
        d, l = get_single_rgbf_extrema( rgbf_list[ i ] )
        
        darkest = min( d, darkest ) 
        lighest = max( l, lighest )

    return darkest, lighest

############################
def test_it():
    image = 'test/test_chunk_00000.tga'
    watermark = 'test/test_chunk_00001.png'

    wmark = Image.open(watermark)
    img = Image.open(image)

    out = ImageChops.add( img, wmark )

    out.save("result.png", "PNG")

    
############################
if __name__ == "__main__":
    ir0, ig0, ib0 = get_bands( t0 )
    ir1, ig1, ib1 = get_bands( t1 )
    
    out_r = ImageChops.add( ir0, ir1 )
    out_g = ImageChops.add( ig0, ig1 )
    out_b = ImageChops.add( ib0, ib1 )
