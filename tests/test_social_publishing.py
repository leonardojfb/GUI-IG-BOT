import pytest

from social_publishing import (
    INSTAGRAM_REEL,
    INSTAGRAM_STORY,
    INSTAGRAM_TRIAL_REEL,
    default_publication_target,
    is_telegram_publication_target,
    normalize_story_link_base,
    resolve_story_link,
    validate_publication_metadata,
)


def test_story_base_and_default_account_link_are_normalized():
    base = normalize_story_link_base("link.ejemplo/")

    assert base == "https://link.ejemplo"
    assert (
        resolve_story_link(base, "nombre.de.cuenta")
        == "https://link.ejemplo/nombre.de.cuenta"
    )


def test_individual_override_wins_only_when_enabled():
    assert (
        resolve_story_link(
            "https://link.ejemplo",
            "alice",
            False,
            "https://custom.ejemplo/a",
        )
        == "https://link.ejemplo/alice"
    )
    assert (
        resolve_story_link(
            "https://link.ejemplo",
            "alice",
            True,
            "https://custom.ejemplo/a",
        )
        == "https://custom.ejemplo/a"
    )


def test_trial_target_and_story_metadata_are_explicit():
    assert default_publication_target("normal") == INSTAGRAM_REEL
    assert default_publication_target("trial") == INSTAGRAM_TRIAL_REEL
    assert is_telegram_publication_target(INSTAGRAM_REEL)
    assert is_telegram_publication_target(INSTAGRAM_TRIAL_REEL)
    assert not is_telegram_publication_target(INSTAGRAM_STORY)

    data = validate_publication_metadata(
        INSTAGRAM_STORY,
        "normal",
        "",
        "https://link.ejemplo/alice",
        "Mira el enlace",
        {},
    )

    assert data["story_announcement_text"] == "Mira el enlace"


def test_story_metadata_requires_link_and_announcement():
    with pytest.raises(ValueError, match="enlace"):
        validate_publication_metadata(
            INSTAGRAM_STORY,
            "normal",
            "",
            "",
            "Mira el enlace",
            {},
        )

    with pytest.raises(ValueError, match="anuncio"):
        validate_publication_metadata(
            INSTAGRAM_STORY,
            "normal",
            "",
            "https://link.ejemplo/alice",
            "",
            {},
        )
