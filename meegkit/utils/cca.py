import numpy as np
from scipy import linalg

from .covariances import cov_lags
from .matrix import _check_shifts
from .denoise import pca


def nt_cca(X=None, Y=None, lags=None, C=None, m=None, thresh=None):
    """Compute CCA from covariance.

    Parameters
    ----------
    X, Y : arrays, shape = (n_times, n_chans[, n_trials])
        Data.
    lags : array, shape = (n_lags,)
        Array of lags. A positive lag means Y delayed relative to X.
    C : array, shape = (n_chans, n_chans[, n_lags])
        Covariance matrix of [X, Y]. C can be 3D, which case CCA is derived
        independently from each page.
    m : int
        Number of channels of X.
    thresh: float
        Discard principal components below this value.

    Returns
    -------
    A : array, shape = (n_chans_X, min(n_chans_X, n_chans_Y))
        Transform matrix mapping `X` to canonical space.
    B : array,  shape = (n_chans_Y, min(n_chans_X, n_chans_Y))
        Transform matrix mapping `Y` to canonical space.
    R : array, shape = (n_comps, n_lags)
        Correlation scores.

    Notes
    -----
    Usage 1: CCA of X, Y
    >> [A, B, R] = nt_cca(X, Y)  # noqa

    Usage 2: CCA of X, Y for each value of lags.
    >> [A, B, R] = nt_cca(X, Y, lags)  # noqa

    A positive lag indicates that Y is delayed relative to X.

    Usage 3: CCA from covariance matrix
    >> C = [X, Y].T * [X, Y]  # noqa
    >> [A, B, R] = nt_cca([], [], [], C, X.shape[1])  # noqa

    Use the third form to handle multiple files or large data (covariance C can
    be calculated chunk-by-chunk).

    .. warning:: Means of X and Y are NOT removed.
    .. warning:: A, B are scaled so that (X * A)^2 and (Y * B)^2 are identity
                 matrices (differs from sklearn).

    See Also
    --------
    nt_cov_lags, nt_relshift, nt_cov, nt_pca in NoiseTools.

    """
    if thresh is None:
        thresh = 1e-12

    if (X is None and Y is not None) or (Y is None and X is not None):
        raise AttributeError('Either *both* X and Y should be defined, or C!')

    if X is not None:
        lags, n_lags = _check_shifts(lags)
        C, _, m = cov_lags(X, Y, lags)
        A, B, R = nt_cca(None, None, None, C, m, thresh)
        return A, B, R

    if C is None:
        raise RuntimeError('covariance matrix should be defined')
    if m is None:
        raise RuntimeError('m should be defined')
    if C.shape[0] != C.shape[1]:
        raise RuntimeError('covariance matrix should be square')
    if any((X, Y, lags)):
        raise RuntimeError('only covariance should be defined at this point')
    if C.ndim > 3:
        raise RuntimeError('covariance should be 3D at most')

    if C.ndim == 3:  # covariance is 3D: do a separate CCA for each trial
        n_chans, _, n_lags = C.shape
        N = np.min((m, n_chans - m))
        A = np.zeros((m, N, n_lags))
        B = np.zeros((n_chans - m, N, n_lags))
        R = np.zeros((N, n_lags))

        for k in np.arange(n_lags):
            AA, BB, RR = nt_cca(None, None, None, C[:, :, k], m, thresh)
            A[:AA.shape[0], :AA.shape[1], k] = AA
            B[:BB.shape[0], :BB.shape[1], k] = BB
            R[:, k] = RR

        return A, B, R

    # Calculate CCA given C = [X,Y].T * [X,Y] and m = x.shape[1]
    # -------------------------------------------------------------------------
    Cxw = whiten_nt(C[:m, :m], thresh)  # sphere X
    Cyw = whiten_nt(C[m:, m:], thresh)  # sphere Y

    # apply sphering matrices to C
    W = np.zeros((Cxw.shape[0] + Cyw.shape[0], Cxw.shape[1] + Cyw.shape[1]))
    W[:Cxw.shape[0], :Cxw.shape[1]] = Cxw
    W[Cxw.shape[0]:, Cxw.shape[1]:] = Cyw
    C = np.dot(np.dot(W.T, C), W)

    # Number of CCA componenets
    N = np.min((Cxw.shape[1], Cyw.shape[1]))

    # PCA
    V, d = pca(C)

    A = np.dot(Cxw, V[:Cxw.shape[1], :N]) * np.sqrt(2)
    B = np.dot(Cyw, V[Cxw.shape[1]:, :N]) * np.sqrt(2)
    R = d[:N] - 1

    return A, B, R


def whiten(C, fudge=1e-18):
    """Whiten covariance matrix C of X.

    If X has shape = (observations, components), X_white = np.dot(X, W).

    References
    ----------
    https://stackoverflow.com/questions/6574782/how-to-whiten-matrix-in-pca

    """
    eigvals, V = linalg.eigh(C)  # eigenvalue decomposition of the covariance

    # a fudge factor can be used so that eigenvectors associated with
    # small eigenvalues do not get overamplified.
    D = np.diag(1. / np.sqrt(eigvals + fudge))
    W = np.dot(np.dot(V, D), V.T)   # whitening matrix

    return W


def whiten_nt(C, thresh=1e-12):
    """Covariance whitening function from noisetools."""
    d, V = linalg.eigh(C)  # eigh if matrix symmetric, eig otherwise
    d = np.real(d)
    V = np.real(V)

    # Sort eigenvalues
    idx = np.argsort(d)[::-1]
    d = d[idx]
    V = V[:, idx]

    # Remove small eigenvalues
    keep = (d / np.max(d)) > thresh
    d = d[keep]
    V = V[:, keep]

    # break symmetry when x and y perfectly correlated (otherwise cols of x*A
    # and y*B are not orthogonal)
    d = d ** (1 - thresh)

    D = np.diag(np.sqrt((1. / d)))
    W = np.dot(V, D)

    return W


def whiten_svd(X):
    """SVD whitening."""
    U, S, Vt = linalg.svd(X, full_matrices=False)

    # U and Vt are the singular matrices, and s contains the singular values.
    # Since the rows of both U and Vt are orthonormal vectors, then U * Vt
    # will be white
    X_white = np.dot(U, Vt)

    return X_white


def whiten_zca(C, thresh=None):
    """Compute ZCA whitening matrix (aka Mahalanobis whitening).

    Parameters
    ----------
    C : array
        Covariance matrix.
    thresh : float
        Whitening constant, it prevents division by zero.

    Returns
    -------
    ZCA: array, shape (n_chans, n_chans)
        ZCA matrix, to be multiplied with data.

    """
    U, S, V = np.linalg.svd(C)  # Singular Value Decomposition

    # ZCA Whitening matrix
    D = np.diag(1. / np.sqrt(S + thresh))
    ZCA = np.dot(np.dot(U, D), U.T)

    return ZCA
