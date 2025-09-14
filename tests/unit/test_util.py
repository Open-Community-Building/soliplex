from unittest import mock

import pytest

from soliplex import util


@pytest.mark.parametrize("to_scrub, expected", [
    ({}, {}),
    ({"foo": "bar"}, {"foo": "bar"}),
    ({"foo": "bar", "_qux": "spam"}, {"foo": "bar"}),
    (
        {"foo": "bar", "baz": {"spam": "qux"}},
        {"foo": "bar", "baz": {"spam": "qux"}},
    ),
    (
        {"foo": "bar", "baz": {"_spam": "qux"}},
        {"foo": "bar", "baz": {}},
    ),
    (
        {"foo": "bar", "spam": []}, {"foo": "bar", "spam": []}
    ),
    (
        {"foo": "bar", "spam": [{"baz": "bam"}]},
        {"foo": "bar", "spam": [{"baz": "bam"}]}
    ),
    (
        {"foo": "bar", "spam": [{"baz": "bam", "_bif": "spaz"}]},
        {"foo": "bar", "spam": [{"baz": "bam"}]}
    ),
])
def test_scrub_private_keys(to_scrub, expected):
    found = util.scrub_private_keys(to_scrub)

    assert found == expected


@pytest.mark.parametrize("source, env_patch, expected", [
    ("no_env_prefix", {}, "no_env_prefix"),
    ("no_env_prefix", {"foo": "bar"}, "no_env_prefix"),
    ("env:{foo}", {"foo": "bar"}, "bar"),
    ("env:Testing {foo}", {"foo": "bar"}, "Testing bar"),
    ("env:{foo}", {"foo": "bar", "baz": "qux"}, "bar"),
    ("env:{baz}-{foo}", {"foo": "bar", "baz": "qux"}, "qux-bar"),
    ("env:Pfx {baz}-{foo}", {"foo": "bar", "baz": "qux"}, "Pfx qux-bar"),
])
def test_interpolate_env_vars(source, env_patch, expected):

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        found = util.interpolate_env_vars(source)

    assert found == expected
