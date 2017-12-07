import os

from apps.rendering.resources.imgverifier import ImgStatistics, \
    ImgVerifier
from apps.rendering.resources.imgrepr import PILImgRepr
from golem.verification.verifier import SubtaskVerificationState

from golem.tools.assertlogs import LogTestCase
from golem import testutils
from golem.core.common import get_golem_path


# to run from console: go to the folder with images and type:
# $ pyssim base_img_name.png '*.png'
# !!! WARNING !!!
# PILImgRepr().load_from_file() runs
# self.img = self.img.convert('RGB') which may change the result!!!

# you can always check the file's color map by typing:
# $ file myImage.png
# myImage.png: PNG image data, 150 x 200, 8-bit/color RGB, non-interlaced


class TestImgVerifier(LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['apps/rendering/resources/imgverifier.py']

    def test_get_random_crop_window(self):
        import random
        random.seed(0)

        random_crop_window_for_verification = \
            ImgVerifier().get_random_crop_window(coverage=0.1,
                                                    window=(0, 1, 0, 1))

        assert random_crop_window_for_verification == (
            0.57739221584148, 0.8936199818583179,
            0.5182681753558643, 0.8344959413727022)

    def test_pilcrop_vs_luxrender_croppingwindow(self):
        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering",
                                   "resources", "pilcrop_vs_cropwindow_test")

        img0 = PILImgRepr()
        img0.load_from_file(os.path.join(
            folder_path, '0.209 0.509 0.709 0.909.png'))
        cropping_window0 = (0.209, 0.509, 0.709, 0.909)

        img1 = PILImgRepr()
        img1.load_from_file(os.path.join(
            folder_path, '0.210 0.510 0.710 0.910.png'))
        cropping_window1 = (0.210, 0.510, 0.710, 0.910)

        img2 = PILImgRepr()
        img2.load_from_file(os.path.join(
            folder_path, '0.211 0.511 0.711 0.911.png'))
        cropping_window2 = (0.211, 0.511, 0.711, 0.911)

        answer_img0 = PILImgRepr()
        answer_img0.load_from_file(
            os.path.join(folder_path,
                         'answer 0.209 0.509 0.709 0.909.png'))

        answer_img1 = PILImgRepr()
        answer_img1.load_from_file(
            os.path.join(folder_path,
                         'answer 0.210 0.510 0.710 0.910.png'))

        answer_img2 = PILImgRepr()
        answer_img2.load_from_file(
            os.path.join(folder_path,
                         'answer 0.211 0.511 0.711 0.911.png'))

        img_verifier = ImgVerifier()

        # act
        cropped_img0 = img_verifier.crop_img_relative(
            img0, cropping_window0)
        cropped_img0.img.save(
            os.path.join(folder_path, 'cropped' + cropped_img0.get_name()))

        cropped_img1 = img_verifier.crop_img_relative(
            img1, cropping_window1)
        cropped_img1.img.save(
            os.path.join(folder_path, 'cropped' + cropped_img1.get_name()))

        cropped_img2 = img_verifier.crop_img_relative(
            img2, cropping_window2)
        cropped_img2.img.save(os.path.join(folder_path,
                                           'cropped' + cropped_img2.get_name()))

        # assert
        import hashlib
        assert hashlib.md5(
            answer_img0.to_pil().tobytes()).hexdigest() == hashlib.md5(
            cropped_img0.to_pil().tobytes()).hexdigest()

        assert hashlib.md5(
            cropped_img1.to_pil().tobytes()).hexdigest() == hashlib.md5(
            answer_img1.to_pil().tobytes()).hexdigest()

        assert hashlib.md5(
            cropped_img2.to_pil().tobytes()).hexdigest() == hashlib.md5(
            answer_img2.to_pil().tobytes()).hexdigest()

    def test_imgStat_values(self):
        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering",
                                   "resources", "imgs_for_verification_tests")

        ref_img0 = PILImgRepr()
        ref_img0.load_from_file(
            os.path.join(folder_path,
                         'reference_300x400spp50_run0.png'))

        ref_img1 = PILImgRepr()
        ref_img1.load_from_file(
            os.path.join(folder_path,
                         'reference_300x400spp50_run1.png'))

        cropping_window = (0.55, 0.75, 0.6, 0.8)
        img_verifier = ImgVerifier()

        # act
        ref_img0 = img_verifier.crop_img_relative(ref_img0, cropping_window)
        ref_img1 = img_verifier.crop_img_relative(ref_img1, cropping_window)

        # these are img rendered by requestor
        reference_stats = ImgStatistics(ref_img0, ref_img1)

        print(reference_stats.get_stats())

        # assert
        assert reference_stats.ssim == 0.73004640056084347
        assert reference_stats.mse == 113.1829861111111
        assert reference_stats.mse_bw == 87.142291666666665
        assert reference_stats.psnr == 27.59299213109294

    def test_is_valid_against_reference(self):
        # arrange
        folder_path = os.path.join(get_golem_path(),
                                   "tests", "apps", "rendering",
                                   "resources", "imgs_for_verification_tests")

        ref_img0 = PILImgRepr()
        ref_img0.load_from_file(os.path.join(folder_path,
                                             'reference_300x400spp50_run0.png'))
        ref_img1 = PILImgRepr()
        ref_img1.load_from_file(os.path.join(folder_path,
                                             'reference_300x400spp50_run1.png'))

        images = list()
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".png") and 'reference' not in file_name:
                p = PILImgRepr()
                p.load_from_file(os.path.join(folder_path, file_name))
                images.append(p)

        cropping_window = (0.55, 0.75, 0.6, 0.8)
        img_verifier = ImgVerifier()

        # act
        ref_img0 = img_verifier.crop_img_relative(ref_img0, cropping_window)
        ref_img1 = img_verifier.crop_img_relative(ref_img1, cropping_window)

        # these are img rendered by requestor
        reference_stats = ImgStatistics(ref_img0, ref_img1)
        #
        # ref_img0.img.save(('aaa' + ref_img0.get_name() + '.png'))
        # ref_img1.img.save(('aaa' + ref_img1.get_name() + '.png'))
        print(reference_stats.get_stats())

        print('SSIM \t\t MSE \t\t MSE_norm \t\t MSE_bw \t\t PSNR')
        imgstats = []
        validation_results = {}

        for img in images:
            croped_img = img_verifier.crop_img_relative(img, cropping_window)
            # croped_img.img.save('aaa'+croped_img.get_name())
            imgstat = ImgStatistics(ref_img0, croped_img)
            validation_result = img_verifier.is_valid_against_reference(
                imgstat, reference_stats)

            imgstats.append(imgstat)
            validation_results[imgstat.name] = validation_result
            print(imgstat.name, imgstat.get_stats(), validation_result)

        # assert
        should_be_rejected = [value for key, value
                              in validation_results.items()
                              if 'malicious' in key.lower()]

        for w in should_be_rejected:
            assert w == SubtaskVerificationState.WRONG_ANSWER

        should_be_verified = [value for key, value
                              in validation_results.items()
                              if 'malicious' not in key.lower()]

        for w in should_be_verified:
            assert w == SubtaskVerificationState.VERIFIED
