import pytest

from poc_poetry_partifact_plugin.plugin import PocPartifactPlugin


@pytest.fixture
def parsed_pyproject_toml_with_non_codeartifact_source() -> dict:
    return {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "url": "https://pypi.org",
                        "name": "my_source_name",
                    }
                ]
            }
        }
    }


@pytest.fixture
def correct_parsed_pyproject_toml() -> dict:
    return {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "url": "https://my-domain-123456789012.d.codeartifact.us-west-2.amazonaws.com/pypi/my-repo/simple/",
                        "name": "my_source_name",
                    }
                ]
            }
        }
    }


@pytest.fixture
def parsed_pyproject_toml_no_name() -> dict:
    return {
        "tool": {
            "poetry": {
                "source": [
                    {
                        "url": "https://my-domain-123456789012.d.codeartifact.us-west-2.amazonaws.com/pypi/my-repo/simple/",
                    }
                ]
            }
        }
    }


def test_object_initialization():
    """Unsure of the best way to test a poetry plugin..."""
    plugin = PocPartifactPlugin()
    assert isinstance(plugin, PocPartifactPlugin)


def test_get_repository(correct_parsed_pyproject_toml):
    plugin = PocPartifactPlugin()

    output = plugin._get_repository(correct_parsed_pyproject_toml)
    assert output == "my_source_name"


def test_get_repository_no_name(parsed_pyproject_toml_no_name):
    plugin = PocPartifactPlugin()

    with pytest.raises(RuntimeError):
        plugin._get_repository(parsed_pyproject_toml_no_name)


def test_pyproject_toml_has_codeartifact(correct_parsed_pyproject_toml):
    plugin = PocPartifactPlugin()

    output = plugin._pyproject_toml_has_codeartifact(correct_parsed_pyproject_toml)

    assert output is True


def test_pyproject_toml_has_codeartifact_missing(
    parsed_pyproject_toml_with_non_codeartifact_source,
):
    plugin = PocPartifactPlugin()

    output = plugin._pyproject_toml_has_codeartifact(
        parsed_pyproject_toml_with_non_codeartifact_source
    )

    assert output is False
