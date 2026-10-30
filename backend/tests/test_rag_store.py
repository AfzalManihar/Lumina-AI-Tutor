import math

import pytest

from app.rag.store import cosine
from app.services.documents import _validate_vectors


def test_cosine_identical_vectors():
    assert cosine([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_dimension_mismatch_is_safe():
    assert cosine([1.0, 2.0], [1.0]) == 0.0


def test_cosine_zero_vector_is_safe():
    assert cosine([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_cosine_non_finite_vector_is_safe():
    assert cosine([math.nan, 1.0], [1.0, 1.0]) == 0.0


def test_validate_vectors_accepts_consistent_vectors():
    assert _validate_vectors([[1.0, 0.0], [0.0, 1.0]], 2) == 2


def test_validate_vectors_rejects_wrong_count():
    with pytest.raises(Exception):
        _validate_vectors([[1.0, 0.0]], 2)


def test_validate_vectors_rejects_mixed_dimensions():
    with pytest.raises(Exception):
        _validate_vectors([[1.0, 0.0], [1.0]], 2)


def test_validate_vectors_rejects_zero_vector():
    with pytest.raises(Exception):
        _validate_vectors([[0.0, 0.0]], 1)


def test_validate_vectors_rejects_non_finite_values():
    with pytest.raises(Exception):
        _validate_vectors([[math.inf, 1.0]], 1)
