"""Utility functions."""
from .base import mldivide, mrdivide
from .covariances import cov_lags, tscov, tsxcov
from .denoise import (find_outlier_trials, find_outliers, mean_over_trials,
                      pca, regcov, wmean, wpwr)
from .matrix import (demean, fold, multishift, multismooth, normcol, relshift,
                     shift, shiftnd, theshapeof, unfold, unsqueeze, widen_mask)
from .sig import (AuditoryFilterbank, GammatoneFilterbank, erb2hz, erbspace,
                  hilbert_envelope, hz2erb, smooth, spectral_envelope)
from .stats import (bootstrap_ci, bootstrap_snr, cronbach, rms, robust_mean,
                    rolling_corr, snr_spectrum)
from .viz import plot_montage
