import typing

from creme import base
from creme import stats


__all__ = ['StatImputer']


class StatImputer(base.Transformer):
    """Replaces missing values with a statistic.

    This transformer allows you to replace missing values with the value of a running statistic.
    During a call to `fit_one`, for each feature, a statistic is updated whenever a numeric feature
    is observed. When `transform_one` is called, each feature with a `None` value is replaced with
    the current value of the corresponding statistic.

    Parameters:
        imputers: A list of tuples where each tuple has two elements. The first elements is a
            feature name and the second value is an instance of `stats.Univariate`. The second
            value can also be an arbitrary value, such as -1, in which case the missing values will
            be replaced with it.

    Example:

        >>> from creme import impute
        >>> from creme import stats

        For numeric data, we can use a `stats.Mean()` to replace missing values by the running
        average of the previously seen values:

        >>> X = [
        ...     {'temperature': 1},
        ...     {'temperature': 8},
        ...     {'temperature': 3},
        ...     {'temperature': None},
        ...     {'temperature': 4}
        ... ]

        >>> imp = impute.StatImputer(('temperature', stats.Mean()))

        >>> for x in X:
        ...     imp = imp.fit_one(x)
        ...     print(imp.transform_one(x))
        {'temperature': 1}
        {'temperature': 8}
        {'temperature': 3}
        {'temperature': 4.0}
        {'temperature': 4}

        For discrete/categorical data, a common practice is to `stats.Mode` to replace missing
        values by the most commonly seen value:

        >>> X = [
        ...     {'weather': 'sunny'},
        ...     {'weather': 'rainy'},
        ...     {'weather': 'sunny'},
        ...     {'weather': None},
        ...     {'weather': 'rainy'},
        ...     {'weather': 'rainy'},
        ...     {'weather': None}
        ... ]

        >>> imp = impute.StatImputer(('weather', stats.Mode()))

        >>> for x in X:
        ...     imp = imp.fit_one(x)
        ...     print(imp.transform_one(x))
        {'weather': 'sunny'}
        {'weather': 'rainy'}
        {'weather': 'sunny'}
        {'weather': 'sunny'}
        {'weather': 'rainy'}
        {'weather': 'rainy'}
        {'weather': 'rainy'}

        You can also choose to replace missing values with a constant value, as so:

        >>> imp = impute.StatImputer(('weather', 'missing'))

        >>> for x in X:
        ...     imp = imp.fit_one(x)
        ...     print(imp.transform_one(x))
        {'weather': 'sunny'}
        {'weather': 'rainy'}
        {'weather': 'sunny'}
        {'weather': 'missing'}
        {'weather': 'rainy'}
        {'weather': 'rainy'}
        {'weather': 'missing'}

        Multiple imputers can be defined by providing a tuple for each feature which you want to
        impute:

        >>> X = [
        ...     {'weather': 'sunny', 'temperature': 8},
        ...     {'weather': 'rainy', 'temperature': 3},
        ...     {'weather': 'sunny', 'temperature': None},
        ...     {'weather': None, 'temperature': 4},
        ...     {'weather': 'snowy', 'temperature': -4},
        ...     {'weather': 'snowy', 'temperature': -3},
        ...     {'weather': 'snowy', 'temperature': -3},
        ...     {'weather': None, 'temperature': None}
        ... ]

        >>> imp = impute.StatImputer(
        ...     ('temperature', stats.Mean()),
        ...     ('weather', stats.Mode())
        ... )

        >>> for x in X:
        ...     imp = imp.fit_one(x)
        ...     print(imp.transform_one(x))
        {'weather': 'sunny', 'temperature': 8}
        {'weather': 'rainy', 'temperature': 3}
        {'weather': 'sunny', 'temperature': 5.5}
        {'weather': 'sunny', 'temperature': 4}
        {'weather': 'snowy', 'temperature': -4}
        {'weather': 'snowy', 'temperature': -3}
        {'weather': 'snowy', 'temperature': -3}
        {'weather': 'snowy', 'temperature': 0.8333}

        A sophisticated way to go about imputation is condition the statistics on a given feature.
        For instance, we might want to replace a missing temperature with the average temperature
        of a particular weather condition. As an example, consider the following dataset where the
        temperature is missing, but not the weather condition:

        >>> X = [
        ...     {'weather': 'sunny', 'temperature': 8},
        ...     {'weather': 'rainy', 'temperature': 3},
        ...     {'weather': 'sunny', 'temperature': None},
        ...     {'weather': 'rainy', 'temperature': 4},
        ...     {'weather': 'sunny', 'temperature': 10},
        ...     {'weather': 'sunny', 'temperature': None},
        ...     {'weather': 'sunny', 'temperature': 12},
        ...     {'weather': 'rainy', 'temperature': None}
        ... ]

        Each missing temperature can be replaced with the average temperature of the corresponding
        weather condition as so:

        >>> from creme import compose

        >>> imp = compose.Grouper(
        ...     impute.StatImputer(('temperature', stats.Mean())),
        ...     by='weather'
        ... )

        >>> for x in X:
        ...     imp = imp.fit_one(x)
        ...     print(imp.transform_one(x))
        {'weather': 'sunny', 'temperature': 8}
        {'weather': 'rainy', 'temperature': 3}
        {'weather': 'sunny', 'temperature': 8.0}
        {'weather': 'rainy', 'temperature': 4}
        {'weather': 'sunny', 'temperature': 10}
        {'weather': 'sunny', 'temperature': 9.0}
        {'weather': 'sunny', 'temperature': 12}
        {'weather': 'rainy', 'temperature': 3.5}

        Note that you can also create a `Grouper` with the `*` operator:

        >>> imp = impute.StatImputer(('temperature', stats.Mean())) * 'weather'

    """

    def __init__(self, *imputers):
        self.stats = {
            feature: stat if isinstance(stat, stats.Univariate) else Constant(stat)
            for feature, stat in imputers
        }

    def fit_one(self, x):

        for i in self.stats:
            if x[i] is not None:
                self.stats[i].update(x[i])

        return self

    def transform_one(self, x):

        # Transformers are supposed to be pure, therefore we make a copy of the features
        x = x.copy()

        for i in self.stats:
            if x[i] is None:
                x[i] = self.stats[i].get()

        return x


class Constant(stats.Univariate):
    """Implements the `stats.Univariate` interface but always returns the same value.

    Parameters:
        value

    """

    def __init__(self, value: typing.Any):
        self.value = value

    def update(self, x):
        return self

    def get(self):
        return self.value

    @property
    def name(self):
        return self.value
