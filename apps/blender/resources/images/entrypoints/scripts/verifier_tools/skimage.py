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

def crop(ar, crop_width, copy=False, order='K'):
    ar = np.array(ar, copy=False)
    crops = _validate_lengths(ar, crop_width)
    slices = tuple(slice(a, ar.shape[i] - b)
                   for i, (a, b) in enumerate(crops))
    if copy:
        cropped = np.array(ar[slices], order=order, copy=True)
    else:
        cropped = ar[slices]
    return cropped

def _assert_compatible(im1, im2):
    if not im1.shape == im2.shape:
        raise ValueError('Input images must have the same dimensions.')
    return

def _as_floats(im1, im2):
    float_type = np.result_type(im1.dtype, im2.dtype, np.float32)
    im1 = np.asarray(im1, dtype=float_type)
    im2 = np.asarray(im2, dtype=float_type)
    return im1, im2

def compare_mse(im1, im2):
    _assert_compatible(im1, im2)
    im1, im2 = _as_floats(im1, im2)
    return np.mean(np.square(im1 - im2), dtype=np.float64)

def compare_psnr(im_true, im_test, data_range=None):
   
    _assert_compatible(im_true, im_test)

    if data_range is None:
        if im_true.dtype != im_test.dtype:
            warn("Inputs have mismatched dtype.  Setting data_range based on "
                 "im_true.")
        dmin, dmax = dtype_range[im_true.dtype.type]
        true_min, true_max = np.min(im_true), np.max(im_true)
        if true_max > dmax or true_min < dmin:
            raise ValueError(
                "im_true has intensity values outside the range expected for "
                "its data type.  Please manually specify the data_range")
        if true_min >= 0:
            # most common case (255 for uint8, 1 for float)
            data_range = dmax
        else:
            data_range = dmax - dmin

    im_true, im_test = _as_floats(im_true, im_test)

    err = compare_mse(im_true, im_test)
    return 10 * np.log10((data_range ** 2) / err)


def compare_ssim(X, Y, win_size=None, gradient=False,
                 data_range=None, multichannel=False, gaussian_weights=False,
                 full=False, **kwargs):
    
    _assert_compatible(X, Y)

    if multichannel:
        # loop over channels
        args = dict(win_size=win_size,
                    gradient=gradient,
                    data_range=data_range,
                    multichannel=False,
                    gaussian_weights=gaussian_weights,
                    full=full)
        args.update(kwargs)
        nch = X.shape[-1]
        mssim = np.empty(nch)
        if gradient:
            G = np.empty(X.shape)
        if full:
            S = np.empty(X.shape)
        for ch in range(nch):
            ch_result = compare_ssim(X[..., ch], Y[..., ch], **args)
            if gradient and full:
                mssim[..., ch], G[..., ch], S[..., ch] = ch_result
            elif gradient:
                mssim[..., ch], G[..., ch] = ch_result
            elif full:
                mssim[..., ch], S[..., ch] = ch_result
            else:
                mssim[..., ch] = ch_result
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

    if win_size is None:
        if gaussian_weights:
            win_size = 11  # 11 to match Wang et. al. 2004
        else:
            win_size = 7   # backwards compatibility

    if np.any((np.asarray(X.shape) - win_size) < 0):
        raise ValueError(
            "win_size exceeds image extent.  If the input is a multichannel "
            "(color) image, set multichannel=True.")

    if not (win_size % 2 == 1):
        raise ValueError('Window size must be odd.')

    if data_range is None:
        if X.dtype != Y.dtype:
            print("Inputs have mismatched dtype.  Setting data_range based on "
                 "X.dtype.")
        dmin, dmax = dtype_range[X.dtype.type]
        data_range = dmax - dmin

    ndim = X.ndim

    if gaussian_weights:
        # sigma = 1.5 to approximately match filter in Wang et. al. 2004
        # this ends up giving a 13-tap rather than 11-tap Gaussian
        filter_func = gaussian_filter
        filter_args = {'sigma': sigma}

    else:
        filter_func = uniform_filter
        filter_args = {'size': win_size}

    # ndimage filters need floating point data
    X = X.astype(np.float64)
    Y = Y.astype(np.float64)

    NP = win_size ** ndim

    # filter has already normalized by NP
    if use_sample_covariance:
        cov_norm = NP / (NP - 1)  # sample covariance
    else:
        cov_norm = 1.0  # population covariance to match Wang et. al. 2004

    # compute (weighted) means
    ux = filter_func(X, **filter_args)
    uy = filter_func(Y, **filter_args)

    # compute (weighted) variances and covariances
    uxx = filter_func(X * X, **filter_args)
    uyy = filter_func(Y * Y, **filter_args)
    uxy = filter_func(X * Y, **filter_args)
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
    pad = (win_size - 1) // 2

    # compute (weighted) mean of ssim
    mssim = crop(S, pad).mean()

    if gradient:
        # The following is Eqs. 7-8 of Avanaki 2009.
        grad = filter_func(A1 / D, **filter_args) * X
        grad += filter_func(-S / B2, **filter_args) * Y
        grad += filter_func((ux * (A2 - A1) - uy * (B2 - B1) * S) / D,
                            **filter_args)
        grad *= (2 / X.size)

        if full:
            return mssim, grad, S
        else:
            return mssim, grad
    else:
        if full:
            return mssim, S
        else:
            return mssim
