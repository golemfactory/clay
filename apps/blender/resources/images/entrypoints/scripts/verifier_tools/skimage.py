# todo review: this file consists of code copied from scikit-image,
#  shouldn't be modified in any way
import numpy as np
from numpy.lib.arraypad import _validate_lengths

from scipy.ndimage import uniform_filter, gaussian_filter

# all methods come from scikit-image
# copied to reduce size of the container
# https://github.com/scikit-image/scikit-image

_integer_types = (np.byte, np.ubyte,          # 8 bits
                  np.short, np.ushort,        # 16 bits
                  np.intc, np.uintc,          # 16 or 32 or 64 bits
                  np.int_, np.uint,           # 32 or 64 bits
                  np.longlong, np.ulonglong)  # 64 bits
_integer_ranges = {t: (np.iinfo(t).min, np.iinfo(t).max)
                   for t in _integer_types}
dtype_range = {np.bool_: (False, True),
               np.bool8: (False, True),
               np.float16: (-1, 1),
               np.float32: (-1, 1),
               np.float64: (-1, 1)}
dtype_range.update(_integer_ranges)


def crop(array, crop_width, copy=False, order='K'):
    array = np.array(array, copy=False)
    crops = _validate_lengths(array, crop_width)
    slices = tuple(slice(a, array.shape[i] - b)
                   for i, (a, b) in enumerate(crops))
    if copy:
        cropped = np.array(array[slices], order=order, copy=True)
    else:
        cropped = array[slices]
    return cropped


def _assert_compatible(image1, image2):
    if not image1.shape == image2.shape:
        raise ValueError('Input images must have the same dimensions.')
    return


def _as_floats(image1, image2):
    float_type = np.result_type(image1.dtype, image2.dtype, np.float32)
    image1 = np.asarray(image1, dtype=float_type)
    image2 = np.asarray(image2, dtype=float_type)
    return image1, image2


def compare_mse(image1, image2):
    _assert_compatible(image1, image2)
    image1, image2 = _as_floats(image1, image2)
    return np.mean(np.square(image1 - image2), dtype=np.float64)


def compare_psnr(image_true, image_test, data_range=None):
   
    _assert_compatible(image_true, image_test)

    if data_range is None:
        if image_true.dtype != image_test.dtype:
            warn("Inputs have mismatched dtype.  Setting data_range based on "
                 "im_true.")
        dmin, dmax = dtype_range[image_true.dtype.type]
        true_min, true_max = np.min(image_true), np.max(image_true)
        if true_max > dmax or true_min < dmin:
            raise ValueError(
                "im_true has intensity values outside the range expected for "
                "its data type.  Please manually specify the data_range")
        if true_min >= 0:
            # most common case (255 for uint8, 1 for float)
            data_range = dmax
        else:
            data_range = dmax - dmin

    image_true, image_test = _as_floats(image_true, image_test)

    err = compare_mse(image_true, image_test)
    return 10 * np.log10((data_range ** 2) / err)


def compare_ssim(image1, image2, window_size=None, gradient=False,
                 data_range=None, multichannel=False, gaussian_weights=False,
                 full=False, **kwargs):
    
    _assert_compatible(image1, image2)

    if multichannel:
        # loop over channels
        args = dict(win_size=window_size,
                    gradient=gradient,
                    data_range=data_range,
                    multichannel=False,
                    gaussian_weights=gaussian_weights,
                    full=full)
        args.update(kwargs)
        number_of_channels = image1.shape[-1]
        mssim = np.empty(number_of_channels)
        if gradient:
            G = np.empty(image1.shape)
        if full:
            S = np.empty(image1.shape)
        for channel in range(number_of_channels):
            channel_result = compare_ssim(
                image1[..., channel],
                image2[..., channel],
                **args
            )
            if gradient and full:
                mssim[..., channel], G[..., channel], S[
                    ..., channel] = channel_result
            elif gradient:
                mssim[..., channel], G[..., channel] = channel_result
            elif full:
                mssim[..., channel], S[..., channel] = channel_result
            else:
                mssim[..., channel] = channel_result
        mssim = mssim.mean()
        if gradient and full:
            return mssim, G, S
        elif gradient:
            return mssim, G
        elif full:
            return mssim, S
        else:
            return mssim

    K1 = kwargs.pop('K1', 0.01)
    K2 = kwargs.pop('K2', 0.03)
    sigma = kwargs.pop('sigma', 1.5)
    if K1 < 0:
        raise ValueError("K1 must be positive")
    if K2 < 0:
        raise ValueError("K2 must be positive")
    if sigma < 0:
        raise ValueError("sigma must be positive")
    use_sample_covariance = kwargs.pop('use_sample_covariance', True)

    if window_size is None:
        if gaussian_weights:
            window_size = 11  # 11 to match Wang et. al. 2004
        else:
            window_size = 7   # backwards compatibility

    if np.any((np.asarray(image1.shape) - window_size) < 0):
        raise ValueError(
            "win_size exceeds image extent.  If the input is a multichannel "
            "(color) image, set multichannel=True.")

    if not (window_size % 2 == 1):
        raise ValueError('Window size must be odd.')

    if data_range is None:
        if image1.dtype != image2.dtype:
            print("Inputs have mismatched dtype.  Setting data_range based on "
                 "X.dtype.")
        dmin, dmax = dtype_range[image1.dtype.type]
        data_range = dmax - dmin

    ndim = image1.ndim

    if gaussian_weights:
        # sigma = 1.5 to approximately match filter in Wang et. al. 2004
        # this ends up giving a 13-tap rather than 11-tap Gaussian
        filter_func = gaussian_filter
        filter_args = {'sigma': sigma}

    else:
        filter_func = uniform_filter
        filter_args = {'size': window_size}

    # ndimage filters need floating point data
    image1 = image1.astype(np.float64)
    image2 = image2.astype(np.float64)

    NP = window_size ** ndim

    # filter has already normalized by NP
    if use_sample_covariance:
        cov_norm = NP / (NP - 1)  # sample covariance
    else:
        cov_norm = 1.0  # population covariance to match Wang et. al. 2004

    # compute (weighted) means
    ux = filter_func(image1, **filter_args)
    uy = filter_func(image2, **filter_args)

    # compute (weighted) variances and covariances
    uxx = filter_func(image1 * image1, **filter_args)
    uyy = filter_func(image2 * image2, **filter_args)
    uxy = filter_func(image1 * image2, **filter_args)
    vx = cov_norm * (uxx - ux * ux)
    vy = cov_norm * (uyy - uy * uy)
    vxy = cov_norm * (uxy - ux * uy)

    R = data_range
    C1 = (K1 * R) ** 2
    C2 = (K2 * R) ** 2

    A1, A2, B1, B2 = ((2 * ux * uy + C1,
                       2 * vxy + C2,
                       ux ** 2 + uy ** 2 + C1,
                       vx + vy + C2))
    D = B1 * B2
    S = (A1 * A2) / D

    # to avoid edge effects will ignore filter radius strip around edges
    pad = (window_size - 1) // 2

    # compute (weighted) mean of ssim
    mssim = crop(S, pad).mean()

    if gradient:
        # The following is Eqs. 7-8 of Avanaki 2009.
        grad = filter_func(A1 / D, **filter_args) * image1
        grad += filter_func(-S / B2, **filter_args) * image2
        grad += filter_func((ux * (A2 - A1) - uy * (B2 - B1) * S) / D,
                            **filter_args)
        grad *= (2 / image1.size)

        if full:
            return mssim, grad, S
        else:
            return mssim, grad
    else:
        if full:
            return mssim, S
        else:
            return mssim
