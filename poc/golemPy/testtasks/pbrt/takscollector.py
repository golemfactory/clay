import glob

import OpenEXR, Imath
from PIL import Image, ImageChops

############################
def print_progress( i, total ):
    print "\rProgress: {} %       ".format( 100.0 * float( i + 1 ) / total ),

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
        return (val * scale) + darkest
    
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

        print_progress( i, len( rgbf_list ) )
    
    print ""

    return darkest, lighest

############################
def compose_final_image( open_exr_files ):
    rgbfs = []

    print "Reading input files"
    for i, open_exr_im_file in enumerate( open_exr_files ):
        rgbf = open_exr_as_rgbf_images( open_exr_im_file )
        rgbfs.append( rgbf )

        print_progress( i, len( open_exr_files ) )

    print "\nFinding extremas for all chunks"
    darkest, lighest = get_list_rgbf_extrema( rgbfs )
   
    rgb8_images = []

    print "Converting chunks to rgb8 images"
    for i, rgbf in enumerate( rgbfs ):
        rgb8_im = convert_rgbf_images_to_rgb8_image( rgbf, lighest, darkest )
        rgb8_images.append( rgb8_im )

        print_progress( i, len( rgbfs ) )

    final_img = rgb8_images[ 0 ]

    print "\nCompositing the final image"
    for i in range( 1, len( rgb8_images ) ):
        final_img = ImageChops.add( final_img, rgb8_images[ i ] )

        print_progress( i, len( rgb8_images ) )

    return final_img

############################
def get_exr_files( path ):
    return glob.glob( path + "/*.exr" )

############################
def test_it():
    image = 'test/test_chunk_00000.tga'
    watermark = 'test/test_chunk_00001.png'

    wmark = Image.open(watermark)
    img = Image.open(image)

    out = ImageChops.add( img, wmark )

    out.save("result.png", "PNG")

#klasa powinna miec add task (ktore otwiera i liczy min/max oraz update na tej podstawie swojego stanu) oraz dodaje chunk do listy i tyle - potem usuwa
#finalize - czyli po ostatnim chunku konwertuje na bazie min/max po kolei wszystkie chunki (ale nie otwiera wszystkich, bo na to jest za malo miejsca)
#kazdy skonwertowany dodaje od razu do final image i tylko ten final jest trzymany w pamieci - troche wolniej bedzie, ale za to nie zabraknie RAMU
#teraz obrazek fullhd podzielony na 1000-2000 chunkow wywali manager pamieci

############################
if __name__ == "__main__":
    
    files = get_exr_files( "test_input_0" )

    print "Compositing {} input files".format( len( files ) )

    fin   = compose_final_image( files )
    fin.save( "result.png", "PNG" )
