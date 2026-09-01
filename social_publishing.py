from urllib.parse import quote, urlparse, urlunparse


INSTAGRAM_REEL = "instagram_reel"
INSTAGRAM_TRIAL_REEL = "instagram_trial_reel"
INSTAGRAM_STORY = "instagram_story"
INSTAGRAM_POST = "instagram_post"
FACEBOOK_PAGE_POST = "facebook_page_post"
FACEBOOK_MARKETPLACE_LISTING = "facebook_marketplace_listing"
FACEBOOK_REEL = "facebook_reel"

PUBLICATION_TARGETS = frozenset(
    {
        INSTAGRAM_REEL,
        INSTAGRAM_TRIAL_REEL,
        INSTAGRAM_STORY,
        INSTAGRAM_POST,
        FACEBOOK_PAGE_POST,
        FACEBOOK_MARKETPLACE_LISTING,
        FACEBOOK_REEL,
    }
)
TELEGRAM_PUBLICATION_TARGETS = frozenset({INSTAGRAM_REEL, INSTAGRAM_TRIAL_REEL})


def default_publication_target(delivery_kind):
    if delivery_kind == "normal":
        return INSTAGRAM_REEL
    if delivery_kind == "trial":
        return INSTAGRAM_TRIAL_REEL
    raise ValueError(f"delivery_kind no soportado: {delivery_kind}")


def is_telegram_publication_target(publication_target):
    return publication_target in TELEGRAM_PUBLICATION_TARGETS


def normalize_story_link_base(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("El dominio de historias debe ser una URL valida.")
    if parsed.path.rstrip("/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "El dominio de historias no puede incluir ruta, query ni fragmento."
        )
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _validated_full_url(value):
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("El enlace de historia debe ser una URL valida.")
    return urlunparse(parsed)


def resolve_story_link(base_url, username, override_enabled=False, override_url=""):
    if override_enabled:
        return _validated_full_url(override_url)
    base = normalize_story_link_base(base_url)
    clean_username = str(username or "").strip()
    if not base or not clean_username:
        return ""
    return f"{base}/{quote(clean_username, safe='._-')}"


def validate_publication_metadata(
    publication_target,
    delivery_kind,
    caption="",
    story_link_url="",
    story_announcement_text="",
    platform_payload=None,
):
    if publication_target not in PUBLICATION_TARGETS:
        raise ValueError(f"publication_target no soportado: {publication_target}")
    if delivery_kind == "trial" and publication_target != INSTAGRAM_TRIAL_REEL:
        raise ValueError("Las publicaciones Trial deben usar instagram_trial_reel.")

    normalized_link = ""
    normalized_announcement = str(story_announcement_text or "").strip()
    if publication_target == INSTAGRAM_STORY:
        normalized_link = _validated_full_url(story_link_url)
        if not normalized_announcement:
            raise ValueError("La historia necesita texto de anuncio.")

    return {
        "caption": str(caption or ""),
        "story_link_url": normalized_link,
        "story_announcement_text": normalized_announcement,
        "platform_payload": platform_payload or {},
    }
