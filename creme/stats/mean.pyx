cimport creme.stats.base

from . import base
from . import summing


cdef class Mean(creme.stats.base.Univariate):
    """Running mean.

    Parameters:
        mean: Initial mean.
        n: Initial sum of weights.

    Attributes:
        mean (float): The current value of the mean.
        n (float): The current sum of weights. If each passed weight was 1, then this is equal to
            the number of seen observations.

    Example:

        >>> from creme import stats

        >>> X = [-5, -3, -1, 1, 3, 5]
        >>> mean = stats.Mean()
        >>> for x in X:
        ...     print(mean.update(x).get())
        -5.0
        -4.0
        -3.0
        -2.0
        -1.0
        0.0

    References:
        1. [West, D. H. D. (1979). Updating mean and variance estimates: An improved method. Communications of the ACM, 22(9), 532-535.](https://people.xiph.org/~tterribe/tmp/homs/West79-_Updating_Mean_and_Variance_Estimates-_An_Improved_Method.pdf)
        2. [Finch, T., 2009. Incremental calculation of weighted mean and variance. University of Cambridge, 4(11-5), pp.41-42.](https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf)

    """

    cpdef Mean update(self, double x, double w=1.):
        self.n += w
        if self.n > 0:
            self.mean += w * (x - self.mean) / self.n
        return self

    cpdef Mean revert(self, double x, double w=1.):
        self.n -= w
        if self.n < 0:
            raise ValueError('Cannot go below 0')
        elif self.n == 0:
            self.mean = 0.
        else:
            self.mean -= w * (x - self.mean) / self.n
        return self

    cpdef double get(self):
        return self.mean


class RollingMean(summing.RollingSum):
    """Running average over a window.

    Parameters:
        window_size: Size of the rolling window.

    Example:

        >>> import creme

        >>> X = [1, 2, 3, 4, 5, 6]

        >>> rmean = creme.stats.RollingMean(window_size=2)
        >>> for x in X:
        ...     print(rmean.update(x).get())
        1.0
        1.5
        2.5
        3.5
        4.5
        5.5

        >>> rmean = creme.stats.RollingMean(window_size=3)
        >>> for x in X:
        ...     print(rmean.update(x).get())
        1.0
        1.5
        2.0
        3.0
        4.0
        5.0

    """

    def get(self):
        return super().get() / len(self) if len(self) > 0 else 0


class BayesianMean(base.Univariate):
    """Estimates a mean using outside information.

    Parameters:
        prior
        prior_weight

    References:
        1. [Additive smoothing](https://www.wikiwand.com/en/Additive_smoothing)
        2. [Bayesian average](https://www.wikiwand.com/en/Bayesian_average)
        3. [Practical example of Bayes estimators](https://www.wikiwand.com/en/Bayes_estimator#/Practical_example_of_Bayes_estimators)

    """

    def __init__(self, prior: float, prior_weight: float):
        self.prior = prior
        self.prior_weight = prior_weight
        self.mean = Mean()

    @property
    def name(self):
        return 'bayes_mean'

    def update(self, x):
        self.mean.update(x)
        return self

    def get(self):

        # Uses the notation from https://www.wikiwand.com/en/Bayes_estimator#/Practical_example_of_Bayes_estimators
        R = self.mean.get()
        v = self.mean.n
        m = self.prior_weight
        C = self.prior

        return (R * v + C * m) / (v + m)
