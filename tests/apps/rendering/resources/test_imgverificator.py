import os


import PIL
#from PIL import Image

from apps.rendering.resources.ImgVerificator import ImgStatistics, ImgVerificator

from apps.core.task.verificator import SubtaskVerificationState as VerificationState
from apps.rendering.resources.imgrepr import load_img, PILImgRepr

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem import testutils
from golem.core.common import get_golem_path


# to run from console: go to the folder with images and type:
# $ pyssim base_img_name.png '*.png'
# !!! WARNING !!! PILImgRepr().load_from_file() runs self.img = self.img.convert('RGB') which may change the result!!!
# you can always check the file's color map by typing:
# $ file myImage.png
# myImage.png: PNG image data, 150 x 200, 8-bit/color RGB, non-interlaced


class TestImgVerificator(LogTestCase,testutils.PEP8MixIn):
    PEP8_FILES = ['apps/rendering/resources/ImgVerificator.py',]
    # def test_display_img_stats(self):
    #     """
    #     Uncomment this test to display img stats...
    #     :return:
    #     """
    #     test_path = os.getcwd()
    #     folder_path = os.path.join(test_path, 'imgs_for_verification_tests')
    #
    #     base_img_name = '300x400spp25_run0.png'
    #     base_img =  PILImgRepr()
    #     base_img.load_from_file(os.path.join(folder_path, base_img_name))
    #
    #     (res_x, res_y) = base_img.get_size()
    #
    #     images = list()
    #     for file_name in os.listdir(folder_path):
    #         if file_name.endswith(".png") and base_img_name not in file_name:
    #             p = PILImgRepr()
    #             p.load_from_file(os.path.join(folder_path, file_name))
    #             r=p.img.resize( (res_x, res_y), PIL.Image.ANTIALIAS) # make it same size as base img
    #             p.load_from_pil_object(r,file_name)
    #             images.append(p)
    #
    #
    #     print 'SSIM \t MSE \t MSE_norm \t PSNR'
    #
    #     imgstats = []
    #     for img in images:
    #         imgstat = ImgStatistics(base_img, img)
    #         imgstats.append(imgstat)
    #         print imgstat.name,  imgstat.get_stats()
    #
    #     pass

    def test_get_random_crop_window(self):
        import random
        random.seed(0)

        random_crop_window_for_verification = ImgVerificator().get_random_crop_window(coverage = 0.1, window=(0,1,0,1))
        assert random_crop_window_for_verification == (0.57739221584148, 0.8936199818583179, 0.5182681753558643, 0.8344959413727022)

    def test_pilcrop_vs_luxrender_croppingwindow(self):

        #arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering", "resources", "pilcrop_vs_cropwindow_test")

        img0 = PILImgRepr()
        img0.load_from_file(os.path.join(folder_path, '0.209 0.509 0.709 0.909.png'))
        cropping_window0 = (0.209, 0.509, 0.709, 0.909)

        img1 = PILImgRepr()
        img1.load_from_file(os.path.join(folder_path, '0.210 0.510 0.710 0.910.png'))
        cropping_window1 = (0.210, 0.510, 0.710, 0.910)

        img2 = PILImgRepr()
        img2.load_from_file(os.path.join(folder_path, '0.211 0.511 0.711 0.911.png'))
        cropping_window2 = (0.211, 0.511, 0.711, 0.911)


        answer_img0 = PILImgRepr()
        answer_img0.load_from_file(os.path.join(folder_path, 'answer 0.209 0.509 0.709 0.909.png'))

        answer_img1 = PILImgRepr()
        answer_img1.load_from_file(os.path.join(folder_path, 'answer 0.210 0.510 0.710 0.910.png'))

        answer_img2 = PILImgRepr()
        answer_img2.load_from_file(os.path.join(folder_path, 'answer 0.211 0.511 0.711 0.911.png'))

        imgVerificator = ImgVerificator()


        # act
        cropped_img0 = imgVerificator.crop_img_relative(img0,cropping_window0)
        cropped_img0.img.save(os.path.join(folder_path,'cropped'+cropped_img0.get_name() ))

        cropped_img1 = imgVerificator.crop_img_relative(img1,cropping_window1)
        cropped_img1.img.save(os.path.join(folder_path,'cropped'+cropped_img1.get_name() ))

        cropped_img2 = imgVerificator.crop_img_relative(img2,cropping_window2)
        cropped_img2.img.save(os.path.join(folder_path,'cropped'+cropped_img2.get_name() ))


        # assert
        import hashlib
        assert hashlib.md5(cropped_img0.to_pil().tobytes()).hexdigest() == hashlib.md5(answer_img0.to_pil().tobytes()).hexdigest()
        assert hashlib.md5(cropped_img1.to_pil().tobytes()).hexdigest() == hashlib.md5(answer_img1.to_pil().tobytes()).hexdigest()
        assert hashlib.md5(cropped_img2.to_pil().tobytes()).hexdigest() == hashlib.md5(answer_img2.to_pil().tobytes()).hexdigest()




    def test_is_valid_against_reference(self):
        #arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering", "resources", "imgs_for_verification_tests")

        ref_img0 = PILImgRepr()
        ref_img0.load_from_file(os.path.join(folder_path, 'cropped_300x400spp25_run0.png'))
        ref_img1 = PILImgRepr()
        ref_img1.load_from_file(os.path.join(folder_path, 'cropped_300x400spp25_run1.png'))

        images = list()
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".png") and 'cropped' not in file_name:
                p = PILImgRepr()
                p.load_from_file(os.path.join(folder_path, file_name))
                images.append(p)


        cropping_window = (0.2, 0.4, 0.7, 0.9)
        imgVerificator = ImgVerificator()

        # act
        ref_img0 = imgVerificator.crop_img_relative(ref_img0,cropping_window)
        ref_img1 = imgVerificator.crop_img_relative(ref_img1,cropping_window)


        reference_stats = ImgStatistics(ref_img0, ref_img1)  # these are img rendered by requestor

        # ref_img0.img.save(('aaa'+ref_img0.get_name()+'.png'))
        # print reference_stats.get_stats()

        print 'SSIM \t MSE \t MSE_norm \t PSNR'
        imgstats = []
        validation_results ={}

        for img in images:
            croped_img=imgVerificator.crop_img_relative(img,cropping_window)
            # croped_img.img.save('aaa'+croped_img.get_name())
            imgstat = ImgStatistics(ref_img0, croped_img)
            validation_result = imgVerificator.is_valid_against_reference(imgstat,reference_stats)

            imgstats.append(imgstat)
            validation_results[imgstat.name] = validation_result
            print imgstat.name, imgstat.get_stats(), validation_result


        # assert GG todo
        # assert reference_stats.ssim == 0.40088751827025393
        # assert reference_stats.mse  == 253.2704861111111
        # assert reference_stats.psnr == 24.094957769434753


        should_be_rejected =  [value for key, value in validation_results.items() if 'malicious' in key.lower()]
        for w in should_be_rejected:
            assert w ==VerificationState.WRONG_ANSWER


        should_be_verified =  [value for key, value in validation_results.items() if 'malicious' not in key.lower()]
        for w in should_be_verified:
            assert w == VerificationState.VERIFIED


    # GG todo delete biednie
    def test_biednie_is_valid_against_reference(self):
        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering", "resources", "imgs_for_verification_tests2")

        ref_img0 = PILImgRepr()
        ref_img0.load_from_file(os.path.join(folder_path, 'reference_640x360_spp50_wedding_Rings_run1.png'))
        ref_img1 = PILImgRepr()
        ref_img1.load_from_file(os.path.join(folder_path, 'reference_640x360_spp50_wedding_Rings_run2.png'))

        images = list()
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".png") and 'reference' not in file_name:
                p = PILImgRepr()
                p.load_from_file(os.path.join(folder_path, file_name))
                images.append(p)

        cropping_window = (0.2, 0.4, 0.7, 0.9)
        imgVerificator = ImgVerificator()

        # act
        ref_img0 = imgVerificator.crop_img_relative(ref_img0, cropping_window)
        ref_img1 = imgVerificator.crop_img_relative(ref_img1, cropping_window)

        reference_stats = ImgStatistics(ref_img0, ref_img1)  # these are img rendered by requestor

        # ref_img0.img.save(('aaa'+ref_img0.get_name()+'.png'))
        print reference_stats.get_stats()

        print 'SSIM \t MSE \t MSE_norm \t PSNR'
        imgstats = []
        validation_results = {}

        for img in images:
            croped_img = imgVerificator.crop_img_relative(img, cropping_window)
            # croped_img.img.save('aaa'+croped_img.get_name())
            imgstat = ImgStatistics(ref_img0, croped_img)
            validation_result = imgVerificator.is_valid_against_reference(imgstat, reference_stats)

            imgstats.append(imgstat)
            validation_results[imgstat.name] = validation_result
            print imgstat.name, imgstat.get_stats(), validation_result

        pass
    #
    #
    #
    # def test_is_valid_against_biednie(self):
    #     #arrange
    #
    #     folder_path = os.path.join(get_golem_path(),
    #                                "tests", "apps", "rendering", "resources", "biednie")
    #
    #     ref_img0 = PILImgRepr()
    #     ref_img0.load_from_file(os.path.join(folder_path, 'reference_task1.png'))
    #     ref_img1 = PILImgRepr()
    #     ref_img1.load_from_file(os.path.join(folder_path, 'reference_task2.png'))
    #
    #
    #
    #     images = list()
    #     for file_name in os.listdir(folder_path):
    #         if file_name.endswith(".png") and 'reference' not in file_name:
    #             p = PILImgRepr()
    #             p.load_from_file(os.path.join(folder_path, file_name))
    #             images.append(p)
    #
    #
    #     # cropping_window = (0.2, 0.4, 0.7, 0.9)
    #     cropping_window = (0.192348293338, 0.639561888838, 0.490618088498, 0.937831683998)
    #     imgVerificator = ImgVerificator()
    #
    #     # act
    #     ref_img0 = imgVerificator.crop_img_relative(ref_img0,cropping_window)
    #     ref_img1 = imgVerificator.crop_img_relative(ref_img1,cropping_window)
    #
    #
    #     reference_stats = ImgStatistics(ref_img0, ref_img1)  # these are img rendered by requestor
    #
    #     ref_img0.img.save(('aaa'+ref_img0.get_name()+'.png'))
    #     ref_img1.img.save(('aaa' + ref_img0.get_name() + '.png'))
    #     # print reference_stats.get_stats()
    #
    #     print 'SSIM \t MSE \t MSE_norm \t PSNR'
    #     imgstats = []
    #     validation_results ={}
    #
    #     for img in images:
    #         croped_img=imgVerificator.crop_img_relative(img,cropping_window)
    #         croped_img.img.save('aaa'+croped_img.get_name())
    #         imgstat = ImgStatistics(ref_img0, croped_img)
    #         validation_result = imgVerificator.is_valid_against_reference(imgstat,reference_stats)
    #
    #         imgstats.append(imgstat)
    #         validation_results[imgstat.name] = validation_result
    #
    #         print imgstat.name, imgstat.get_stats(), validation_result
    #
    #
    #     # assert
    #     assert reference_stats.ssim == 0.40088751827025393
    #     assert reference_stats.mse  == 253.2704861111111
    #     assert reference_stats.psnr == 24.094957769434753
    #
    #
    #     should_be_rejected =  [value for key, value in validation_results.items() if 'malicious' in key.lower()]
    #     for w in should_be_rejected:
    #         assert w ==VerificationState.WRONG_ANSWER
    #
    #
    #     should_be_verified =  [value for key, value in validation_results.items() if 'malicious' not in key.lower()]
    #     for w in should_be_verified:
    #         assert w == VerificationState.VERIFIED
    #
