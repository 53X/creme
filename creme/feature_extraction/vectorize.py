import collections
import functools
import itertools
import math
import operator
import re
import typing
import unicodedata

from creme import base


__all__ = ['BagOfWords', 'TFIDF']


N_GRAM = typing.Union[
    str,  # unigram
    typing.Tuple[str, ...]  # n-gram
]


def strip_accents_unicode(s: str) -> str:
    """Transform accentuated unicode symbols into their ASCII counterpart."""
    try:
        # If `s` is ASCII-compatible, then it does not contain any accented
        # characters and we can avoid an expensive list comprehension
        s.encode('ASCII', errors='strict')
        return s
    except UnicodeEncodeError:
        normalized = unicodedata.normalize('NFKD', s)
        return ''.join([c for c in normalized if not unicodedata.combining(c)])


def find_ngrams(tokens: typing.List[str], n: int) -> typing.Iterator[N_GRAM]:
    """Generates n-grams from a list of tokens.

    From http://www.locallyoptimal.com/blog/2013/01/20/elegant-n-gram-generation-in-python/.

    Example:

        >>> tokens = ['a', 'b', 'c']

        >>> list(find_ngrams(tokens, 0))
        []

        >>> list(find_ngrams(tokens, 1))
        ['a', 'b', 'c']

        >>> list(find_ngrams(tokens, 2))
        [('a', 'b'), ('b', 'c')]

        >>> list(find_ngrams(tokens, 3))
        [('a', 'b', 'c')]

        >>> list(find_ngrams(tokens, 4))
        []

    """
    if n == 1:
        return iter(tokens)
    return zip(*[tokens[i:] for i in range(n)])


def find_all_ngrams(tokens: typing.List[str], ngram_range: range) -> typing.Iterator[N_GRAM]:
    """Generates all n-grams in a given range.

    Example:

        >>> tokens = ['a', 'b', 'c']

        >>> list(find_all_ngrams(tokens, range(2)))
        ['a', 'b', 'c']

        >>> list(find_all_ngrams(tokens, range(1, 4)))
        ['a', 'b', 'c', ('a', 'b'), ('b', 'c'), ('a', 'b', 'c')]

    """
    return itertools.chain(*(find_ngrams(tokens, n) for n in ngram_range))


class VectorizerMixin:
    """Contains common processing steps used by each vectorizer.

    Parameters:
        on: The name of the feature that contains the text to vectorize. If `None`, then each
            `fit_one` and `transform_one` should treat `x` as a `str` and not as a `dict`.
        strip_accents: Whether or not to strip accent characters.
        lowercase: Whether or not to convert all characters to lowercase.
        preprocessor: Override the preprocessing step while preserving the tokenizing
            and n-grams generation steps.
        tokenizer: A function used to convert preprocessed text into a `dict` of tokens.
            A default tokenizer is used if `None` is passed. Set to `False` to disable
            tokenization.
        ngram_range: The lower and upper boundary of the range n-grams to be
            extracted. All values of n such that `min_n <= n <= max_n` will be used. For example
            an `ngram_range` of `(1, 1)` means only unigrams, `(1, 2)` means unigrams and
            bigrams, and `(2, 2)` means only bigrams.

    Attributes:
        processing_steps (list): A list of preprocessing steps that are applied to each text.

    """

    def __init__(self, on: str = None, strip_accents=True, lowercase=True,
                 preprocessor: typing.Callable = None,
                 tokenizer: typing.Callable = None, ngram_range=(1, 1)):
        self.on = on
        self.strip_accents = strip_accents
        self.lowercase = lowercase
        self.preprocessor = preprocessor
        self.tokenizer = re.compile(r'(?u)\b\w\w+\b').findall if tokenizer is None else tokenizer
        self.ngram_range = ngram_range

        self.processing_steps = []

        # Text extraction
        if on is not None:
            self.processing_steps.append(operator.itemgetter(on))

        # Preprocessing
        if preprocessor is not None:
            self.processing_steps.append(preprocessor)
        else:
            if self.strip_accents:
                self.processing_steps.append(strip_accents_unicode)
            if self.lowercase:
                self.processing_steps.append(str.lower)

        # Tokenization
        if self.tokenizer:
            self.processing_steps.append(self.tokenizer)

        # n-grams
        if ngram_range[1] > 1:
            self.processing_steps.append(functools.partial(
                find_all_ngrams,
                ngram_range=range(ngram_range[0], ngram_range[1] + 1)
            ))

    def process_text(self, x):
        for step in self.processing_steps:
            x = step(x)
        return x

    def _more_tags(self):
        if self.on is None:
            return {base.tags.TEXT_INPUT}
        return {}


class BagOfWords(base.Transformer, VectorizerMixin):
    """Counts tokens in sentences.

    This transformer can be used to counts tokens in a given piece of text. It takes care of
    normalizing the text before tokenizing it.

    Note that the parameters are identical to those of `feature_extraction.TFIDF`.

    Parameters:
        on: The name of the feature that contains the text to vectorize. If `None`, then each
            `fit_one` and `transform_one` will assume that each `x` that is provided is a `str`,
            andnot a `dict`.
        strip_accents: Whether or not to strip accent characters.
        lowercase: Whether or not to convert all characters to lowercase.
        preprocessor: Override the preprocessing step while preserving the tokenizing and n-grams
            generation steps.
        tokenizer: A function used to convert preprocessed text into a `dict` of tokens. By
            default, a regex formula that works well in most cases is used.
        ngram_range: The lower and upper boundary of the range n-grams to be
            extracted. All values of n such that `min_n <= n <= max_n` will be used. For example
            an `ngram_range` of `(1, 1)` means only unigrams, `(1, 2)` means unigrams and
            bigrams, and `(2, 2)` means only bigrams.

    Example:

        By default, `BagOfWords` will take as input a sentence, preprocess it, tokenize the
        preprocessed text, and then return a `collections.Counter` containing the number of
        occurrences of each token.

        >>> from creme import feature_extraction as fx

        >>> corpus = [
        ...     'This is the first document.',
        ...     'This document is the second document.',
        ...     'And this is the third one.',
        ...     'Is this the first document?',
        ... ]

        >>> bow = fx.BagOfWords()

        >>> for sentence in corpus:
        ...     print(bow.transform_one(sentence))
        Counter({'this': 1, 'is': 1, 'the': 1, 'first': 1, 'document': 1})
        Counter({'document': 2, 'this': 1, 'is': 1, 'the': 1, 'second': 1})
        Counter({'and': 1, 'this': 1, 'is': 1, 'the': 1, 'third': 1, 'one': 1})
        Counter({'is': 1, 'this': 1, 'the': 1, 'first': 1, 'document': 1})

        Note that `fit_one` does not have to be called because `BagOfWords` is stateless. You can
        call it but it won't do anything.

        In the above example, a string is passed to `transform_one`. You can also indicate which
        field to access if the string is stored in a dictionary:

        >>> bow = fx.BagOfWords(on='sentence')

        >>> for sentence in corpus:
        ...     x = {'sentence': sentence}
        ...     print(bow.transform_one(x))
        Counter({'this': 1, 'is': 1, 'the': 1, 'first': 1, 'document': 1})
        Counter({'document': 2, 'this': 1, 'is': 1, 'the': 1, 'second': 1})
        Counter({'and': 1, 'this': 1, 'is': 1, 'the': 1, 'third': 1, 'one': 1})
        Counter({'is': 1, 'this': 1, 'the': 1, 'first': 1, 'document': 1})

        The `ngram_range` parameter can be used to extract n-grams (including unigrams):

        >>> ngrammer = fx.BagOfWords(ngram_range=(1, 2))

        >>> ngrams = ngrammer.transform_one('I love the smell of napalm in the morning')
        >>> for ngram, count in ngrams.items():
        ...     print(ngram, count)
        love 1
        the 2
        smell 1
        of 1
        napalm 1
        in 1
        morning 1
        ('love', 'the') 1
        ('the', 'smell') 1
        ('smell', 'of') 1
        ('of', 'napalm') 1
        ('napalm', 'in') 1
        ('in', 'the') 1
        ('the', 'morning') 1

    """

    def transform_one(self, x):
        return collections.Counter(self.process_text(x))


class TFIDF(BagOfWords):
    """Computes TF-IDF values from sentences.

    The TF-IDF formula is the same one as scikit-learn. The only difference is the fact that the
    document frequencies are determined online, whereas in a batch setting they can be determined
    by performing an initial pass through the data.

    Note that the parameters are identical to those of `feature_extraction.BagOfWords`.

    Parameters:
        normalize: Whether or not the TF-IDF values by their L2 norm.
        on: The name of the feature that contains the text to vectorize. If `None`, then
            the input is treated as a document instead of a set of features.
        strip_accents: Whether or not to strip accent characters.
        lowercase: Whether or not to convert all characters to lowercase.
        preprocessor: Override the preprocessing step while preserving the tokenizing and n-grams
            generation steps.
        tokenizer: A function used to convert preprocessed text into a `dict` of tokens. By
            default, a regex formula that works well in most cases is used.
        ngram_range: The lower and upper boundary of the range n-grams to be
            extracted. All values of n such that `min_n <= n <= max_n` will be used. For example
            an `ngram_range` of `(1, 1)` means only unigrams, `(1, 2)` means unigrams and
            bigrams, and `(2, 2)` means only bigrams. Only works if `tokenizer` is not set to
            `False`.

    Attributes:
        dfs (collections.defaultdict): Document counts.
        n (int): Number of scanned documents.

    Example:

        >>> from creme import feature_extraction

        >>> tfidf = feature_extraction.TFIDF()

        >>> corpus = [
        ...     'This is the first document.',
        ...     'This document is the second document.',
        ...     'And this is the third one.',
        ...     'Is this the first document?',
        ... ]

        >>> for sentence in corpus:
        ...     tfidf = tfidf.fit_one(sentence)
        ...     print(tfidf.transform_one(sentence))
        {'this': 0.447, 'is': 0.447, 'the': 0.447, 'first': 0.447, 'document': 0.447}
        {'this': 0.333, 'document': 0.667, 'is': 0.333, 'the': 0.333, 'second': 0.469}
        {'and': 0.497, 'this': 0.293, 'is': 0.293, 'the': 0.293, 'third': 0.497, 'one': 0.497}
        {'is': 0.384, 'this': 0.384, 'the': 0.384, 'first': 0.580, 'document': 0.469}

        In the above example, a string is passed to `transform_one`. You can also indicate which
        field to access if the string is stored in a dictionary:

        >>> tfidf = feature_extraction.TFIDF(on='sentence')

        >>> for sentence in corpus:
        ...     x = {'sentence': sentence}
        ...     tfidf = tfidf.fit_one(x)
        ...     print(tfidf.transform_one(x))
        {'this': 0.447, 'is': 0.447, 'the': 0.447, 'first': 0.447, 'document': 0.447}
        {'this': 0.333, 'document': 0.667, 'is': 0.333, 'the': 0.333, 'second': 0.469}
        {'and': 0.497, 'this': 0.293, 'is': 0.293, 'the': 0.293, 'third': 0.497, 'one': 0.497}
        {'is': 0.384, 'this': 0.384, 'the': 0.384, 'first': 0.580, 'document': 0.469}

    """

    def __init__(self, normalize=True, on: str = None, strip_accents=True, lowercase=True,
                 preprocessor: typing.Callable = None, tokenizer: typing.Callable = None,
                 ngram_range=(1, 1)):
        super().__init__(
            on=on,
            strip_accents=strip_accents,
            lowercase=lowercase,
            preprocessor=preprocessor,
            tokenizer=tokenizer,
            ngram_range=ngram_range
        )
        self.normalize = normalize
        self.dfs = collections.Counter()
        self.n = 0

    def fit_one(self, x):

        # Update the document counts
        terms = self.process_text(x)
        self.dfs.update(set(terms))

        # Increment the global document counter
        self.n += 1

        return self

    def transform_one(self, x):

        term_counts = super().transform_one(x)
        n_terms = sum(term_counts.values())

        tfidfs = {}

        for term, count in term_counts.items():
            tf = count / n_terms
            idf = math.log(((1 + self.n) / (1 + self.dfs[term]))) + 1
            tfidfs[term] = tf * idf

        if self.normalize:
            norm = math.sqrt(sum(tfidf ** 2 for tfidf in tfidfs.values()))
            return {term: tfidf / norm for term, tfidf in tfidfs.items()}
        return tfidfs
