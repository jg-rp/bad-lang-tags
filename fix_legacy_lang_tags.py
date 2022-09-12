import json
import logging
import sys

from typing import Any
from typing import Dict
from typing import Iterable

import requests

from bot_login import login

from find_bad_lang_tags import BadLangTag
from find_bad_lang_tags import ap_find_bad_lang_tags
from find_bad_lang_tags import get_session

logging.basicConfig(level=logging.DEBUG)


def post_page_edit(
    session: requests.Session,
    url: str,
    csrf_token: str,
    start_timestamp: str,
    wiki_text: str,
    page_id: int,
    revision_id: int,
    revision_timestamp: str,
):
    params = {
        "action": "edit",
        "bot": "true",
        "minor": "true",
        "pageid": page_id,
        "baserevid": revision_id,
        "basetimestamp": revision_timestamp,
        "starttimestamp": start_timestamp,
        "format": "json",
        "text": wiki_text,
        "summary": "auto syntax highlight fix",
        "token": csrf_token,
    }

    resp = session.post(url, data=params)
    resp.raise_for_status()

    logging.debug(json.dumps(resp.json(), indent=4))


class NoLegacyTagsError(Exception):
    """Exception raised when no legacy lang tags are found in a page."""


def replace_legacy_lang(
    wiki_text: str,
    page: Dict[str, Any],
    tags: Iterable[BadLangTag],
) -> str:
    legacy_tags = [t for t in tags if t.kind in ("LANG", "BARE")]
    if not legacy_tags:
        # Force the caller to deal with this.
        raise NoLegacyTagsError(page["title"])

    parts = []
    idx = 0

    for tag in legacy_tags:
        assert tag.end
        lang = tag.lang.strip().lower() if tag.lang else None
        parts.append(wiki_text[idx : tag.start.start])
        if lang:
            parts.append(f'<syntaxhighlight lang="{lang}">')
        else:
            # note that we're not setting a lang attribute if the legacy
            # tag did not have one.
            parts.append(f"<syntaxhighlight>")
        idx = tag.start.end
        parts.append(wiki_text[idx : tag.end.start])
        parts.append("</syntaxhighlight>")
        idx = tag.end.end

    parts.append(wiki_text[idx:])
    return "".join(parts)


# TODO: other AP options
def replace_one(
    session: requests.Session,
    csrf_token: str,
    start_timestamp: str,
    url: str,
    prefix: str,
):
    _tags = list(
        ap_find_bad_lang_tags(
            session,
            url=url,
            prefix=prefix,
            namespace=0,
        )
    )

    assert len(_tags) == 1
    page, tags = _tags[0]

    old_wiki_text = page["revisions"][0]["slots"]["main"]["content"]
    new_wiki_text = replace_legacy_lang(old_wiki_text, page, tags)
    assert old_wiki_text.count("\n") == new_wiki_text.count("\n")

    revision = page["revisions"][0]

    post_page_edit(
        session,
        url,
        csrf_token,
        start_timestamp,
        new_wiki_text,
        page["pageid"],
        revision["revid"],
        revision["timestamp"],
    )


if __name__ == "__main__":
    raise Exception(
        f"{sys.argv[0]} is incomplete and is not being actively developed. "
        "You can create an issue at https://github.com/jg-rp/bad-lang-tags/issues "
        "if you'd like to see this script completed."
    )
    # URL = "https://rosettacode.org/w/api.php"
    # PREFIX = "Define a primitive data type"  # XXX

    # session, csrf_token, start_timestamp = login(
    #     get_session(), URL, sys.argv[1], sys.argv[2]
    # )

    # replace_one(
    #     session,
    #     csrf_token,
    #     start_timestamp,
    #     URL,
    #     PREFIX,
    # )
