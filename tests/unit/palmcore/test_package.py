import pytest

import palmcore
import palmgen
import palmscan
from palmcore import errors


def test_packages_import_with_version() -> None:
    assert palmcore.__version__ == "0.1.0"
    assert palmscan.__version__ == "0.1.0"
    assert palmgen.__version__ == "0.1.0"


@pytest.mark.parametrize(
    ("cls", "code"),
    [
        (errors.PalmfixError, 1),
        (errors.ConfigError, 2),
        (errors.ContractError, 3),
        (errors.SourceError, 4),
        (errors.CacheMiss, 5),
        (errors.ExternalToolError, 6),
    ],
)
def test_exception_exit_codes(cls: type[errors.PalmfixError], code: int) -> None:
    assert issubclass(cls, errors.PalmfixError)
    assert cls.exit_code == code


def test_cache_miss_is_source_error() -> None:
    assert issubclass(errors.CacheMiss, errors.SourceError)


def test_contract_error_stores_issues() -> None:
    assert errors.ContractError("bad", ["a", "b"]).issues == ["a", "b"]
    assert errors.ContractError("bad").issues == []


def test_exit_constants() -> None:
    assert errors.EXIT_OK == 0
    assert errors.EXIT_INTERRUPTED == 130
