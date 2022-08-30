import csv
import itertools
import json
import logging
import re
import sys

from typing import Any
from typing import Dict
from typing import TextIO
from typing import Iterable
from typing import Optional
from typing import Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.adapters import Retry

from pygments import lexers


logging.basicConfig(level=logging.DEBUG)


ALL_LEXERS = set(itertools.chain.from_iterable(l[1] for l in lexers.get_all_lexers()))


AP_QUERY: Dict[str, Any] = {
    "action": "query",
    "generator": "allpages",
    "gapfilterredir": "nonredirects",
    "format": "json",
    "formatversion": "2",
    "prop": "revisions",
    "rvprop": "content|timestamp|ids",
    "rvslots": "main",
}

CM_QUERY: Dict[str, Any] = {
    "action": "query",
    "generator": "categorymembers",
    "format": "json",
    "formatversion": "2",
    "prop": "revisions",
    "rvprop": "content|timestamp|ids",
    "rvslots": "main",
}


RE_SPEC = [
    ("NOWIKI", r"<nowiki\s*>.*?</nowiki\s*>"),
    ("COMMENT", r"<!--.*?-->"),
    ("PRE", r"<pre\s*>.*?</pre\s*>"),
    ("CODE", r"<code\s*>.*?</code\s*>"),
    (
        "HIGH",
        (
            r"(?P<start_high><syntaxhighlight\s+.*?"
            r"lang\s*=\s*"
            r"(?P<attr_quote>[\"'])"
            r"(?P<hl_lang>[^\s>]+)"
            r"(?P=attr_quote)"
            r".*?\s*>).*?"
            r"(?P<end_high></syntaxhighlight\s*>)"
        ),
    ),
    (
        "HIGH_NQ",
        (
            r"(?P<start_high_nq><syntaxhighlight\s+.*?"
            r"lang\s*=\s*"
            r"(?P<hl_lang_nq>[^\s>]+)"
            r".*?\s*>).*?"
            r"(?P<end_high_nq></syntaxhighlight\s*>)"
        ),
    ),
    (
        "BAREHIGH",
        (
            r"(?P<start_bare_high><syntaxhighlight\s*>)"
            r".*?"
            r"(?P<end_bare_high></syntaxhighlight\s*>)"
        ),
    ),
    ("LANG", r"(?P<start><lang\s+(?P<lang>[^\n\r]+?)\s*>).*?(?P<end></lang\s*>)"),
    ("BARE", r"(?P<start_bare><lang\s*>).*?(?P<end_bare></lang\s*>)"),
    ("LONELANG", r"</?lang(?P<lone_lang>\s+[^\n\r]+?)?\s*>"),
    (
        "STARTHIGH",
        (
            r"<syntaxhighlight\s+.+?"
            r"lang\s*=\s*"
            r"(?P<s_attr_quote>[\"']?)"
            r"(?P<s_hl_lang>[^\s>]+)"
            r"(?P=s_attr_quote)"
            r".*?\s*>"
        ),
    ),
    ("ENDHIGH", r"</syntaxhighlight\s*>"),
]

RE_BAD_LANG = re.compile(
    "|".join(rf"(?P<{name}>{pattern})" for name, pattern in RE_SPEC),
    re.DOTALL | re.IGNORECASE,
)


def cm_query(
    session: requests.Session,
    category: str,
    *,
    url: str,
    chunk_size: int = 20,
    limit: int = 50,
) -> Iterable[Dict[str, Any]]:
    page_count = 0
    params: Dict[str, Any] = {
        **CM_QUERY,
        "gcmtitle": category,
        "gcmlimit": chunk_size,
        "continue": None,
    }

    response = session.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    handle_warnings_and_errors(data)

    if data.get("continue", {}).get("gcmcontinue"):
        params["gcmcontinue"] = data["continue"]["gcmcontinue"]
        params["continue"] = data["continue"]["continue"]
        logging.debug("continue from %s", params["gcmcontinue"])

    page_count += len(data["query"]["pages"])
    yield from data["query"]["pages"]

    stop = False

    while page_count < limit and not stop:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("continue", {}).get("gcmcontinue"):
            params["gcmcontinue"] = data["continue"]["gcmcontinue"]
            params["continue"] = data["continue"]["continue"]
            logging.debug("continue from %s", params["gcmcontinue"])
        else:
            stop = True

        num_pages = len(data["query"]["pages"])
        page_count += num_pages
        logging.debug("received %d pages", num_pages)
        yield from data["query"]["pages"]


def ap_query(
    session: requests.Session,
    *,
    url: str,
    prefix: str = "",
    namespace: int = 0,
    chunk_size: int = 25,
    limit: int = 200,
) -> Iterable[Dict[str, Any]]:
    page_count = 0
    params: Dict[str, Any] = {
        **AP_QUERY,
        "gaplimit": chunk_size,
        "gapnamespace": namespace,
        "continue": None,
    }

    if prefix:
        params["gapprefix"] = prefix

    response = session.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    handle_warnings_and_errors(data)

    if data.get("continue", {}).get("gapcontinue"):
        params["gapcontinue"] = data["continue"]["gapcontinue"]
        params["continue"] = data["continue"]["continue"]
        logging.debug("continue from %s", params["gapcontinue"])

    page_count += len(data["query"]["pages"])
    yield from data["query"]["pages"]

    stop = False

    while page_count < limit and not stop:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("continue", {}).get("gapcontinue"):
            params["gapcontinue"] = data["continue"]["gapcontinue"]
            params["continue"] = data["continue"]["continue"]
            logging.debug("continue from %s", params["gapcontinue"])
        else:
            stop = True

        num_pages = len(data["query"]["pages"])
        page_count += num_pages
        logging.debug("received %d pages", num_pages)
        yield from data["query"]["pages"]


def handle_warnings_and_errors(data: Any) -> None:
    if data.get("errors"):
        for error in data["errors"]:
            logging.error(json.dumps(error))
    # legacy format
    if data.get("error"):
        logging.error(json.dumps(data["error"]))
    if data.get("warnings"):
        for warning in data["warnings"]:
            logging.warning(json.dumps(warning))


class LangTagMatch:
    def __init__(self, text: str, start: int, end: int, lineno: int) -> None:
        self.text = text
        self.start = start
        self.end = end
        self.lineno = lineno


class BadLangTag:
    def __init__(
        self,
        lang: Optional[str],
        tag: str,
        start: LangTagMatch,
        end: Optional[LangTagMatch],
        kind: str,
    ):
        self.lang = lang
        self.tag = tag
        self.start = start
        self.end = end
        self.kind = kind


def find_bad_lang_tags(
    wiki_text: str,
    skip_unsupported_langs: bool = False,
) -> Iterable[BadLangTag]:
    for match in RE_BAD_LANG.finditer(wiki_text):
        kind = match.lastgroup

        if kind == "HIGH":
            lang = match.group("hl_lang")
            if skip_unsupported_langs or lang.strip().lower() in ALL_LEXERS:
                continue

            start = match.group("start_high")
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )

            end = match.group("end_high")
            end_match = LangTagMatch(
                text=end,
                start=match.end() - len(end),
                end=match.end(),
                lineno=wiki_text[: match.end() - len(end)].count("\n") + 1,
            )

            yield BadLangTag(
                lang=lang,
                tag="highlight",
                start=start_match,
                end=end_match,
                kind="HIGH",
            )

        if kind == "HIGH_NQ":
            lang = match.group("hl_lang_nq")
            if skip_unsupported_langs or lang.strip().lower() in ALL_LEXERS:
                continue

            start = match.group("start_high_nq")
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )

            end = match.group("end_high_nq")
            end_match = LangTagMatch(
                text=end,
                start=match.end() - len(end),
                end=match.end(),
                lineno=wiki_text[: match.end() - len(end)].count("\n") + 1,
            )

            yield BadLangTag(
                lang=lang,
                tag="highlight",
                start=start_match,
                end=end_match,
                kind="HIGH_NQ",
            )

        if kind == "LANG":
            start = match.group("start")
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )
            end = match.group("end")
            end_match = LangTagMatch(
                text=end,
                start=match.end() - len(end),
                end=match.end(),
                lineno=wiki_text[: match.end() - len(end)].count("\n") + 1,
            )

            yield BadLangTag(
                lang=match.group("lang"),
                tag="lang",
                start=start_match,
                end=end_match,
                kind="LANG",
            )

        elif kind == "BAREHIGH":
            start = match.group("start_bare_high")
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )
            end = match.group("end_bare_high")
            end_match = LangTagMatch(
                text=end,
                start=match.end() - len(end),
                end=match.end(),
                lineno=wiki_text[: match.end() - len(end)].count("\n") + 1,
            )

            yield BadLangTag(
                lang=None,
                tag="highlight",
                start=start_match,
                end=end_match,
                kind="BAREHIGH",
            )

        elif kind == "BARE":
            start = match.group("start_bare")
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )
            end = match.group("end_bare")
            end_match = LangTagMatch(
                text=end,
                start=match.end() - len(end),
                end=match.end(),
                lineno=wiki_text[: match.end() - len(end)].count("\n") + 1,
            )

            yield BadLangTag(
                lang=None,
                tag="lang",
                start=start_match,
                end=end_match,
                kind="BARE",
            )

        elif kind == "LONELANG":
            start = match.group(0)
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )

            yield BadLangTag(
                lang=match.group("lone_lang"),
                tag="/lang" if start.startswith("</") else "lang",
                start=start_match,
                end=None,
                kind="LONELANG",
            )

        elif kind == "STARTHIGH":
            start = match.group(0)
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )

            yield BadLangTag(
                lang=match.group("hl_lang"),
                tag="highlight",
                start=start_match,
                end=None,
                kind="STARTHIGH",
            )

        elif kind == "ENDHIGH":
            start = match.group(0)
            start_match = LangTagMatch(
                text=start,
                start=match.start(),
                end=match.start() + len(start),
                lineno=wiki_text[: match.start()].count("\n") + 1,
            )

            yield BadLangTag(
                lang=None,
                tag="/highlight",
                start=start_match,
                end=None,
                kind="ENDHIGH",
            )


def get_session() -> requests.Session:
    """Setup a requests.Session with retries."""
    retry_strategy = Retry(
        total=5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def cm_find_bad_lang_tags(
    session: requests.Session,
    category: str,
    *,
    url: str,
    chunk_size: int = 20,
    page_limit: int = 60,
    skip_unsupported_langs: bool = True,
) -> Iterable[Tuple[Dict[str, Any], Iterable[BadLangTag]]]:
    pages = cm_query(
        session,
        category,
        url=url,
        chunk_size=chunk_size,
        limit=page_limit,
    )
    for page in pages:
        if not page.get("revisions"):
            logging.error(
                f"missing revision data for '{page}', try reducing chunk_size"
            )
            sys.exit(1)

        content_format = page["revisions"][0]["slots"]["main"]["contentformat"]
        if not content_format == "text/x-wiki":
            logging.error(f"can't handle format {content_format} for '{page}'")
            sys.exit(1)

        yield page, find_bad_lang_tags(
            page["revisions"][0]["slots"]["main"]["content"],
            skip_unsupported_langs,
        )


def ap_find_bad_lang_tags(
    session: requests.Session,
    *,
    url: str,
    prefix: str = "",
    namespace: int = 0,
    chunk_size: int = 20,
    page_limit: int = 60,
    skip_unsupported_langs: bool = True,
) -> Iterable[Tuple[Dict[str, Any], Iterable[BadLangTag]]]:
    pages = ap_query(
        session,
        url=url,
        prefix=prefix,
        namespace=namespace,
        chunk_size=chunk_size,
        limit=page_limit,
    )

    for page in pages:
        if not page.get("revisions"):
            logging.error(
                f"missing revision data for '{page}', try reducing chunk_size"
            )
            sys.exit(1)

        content_format = page["revisions"][0]["slots"]["main"]["contentformat"]
        if not content_format == "text/x-wiki":
            logging.error(f"can't handle format {content_format} for '{page}'")
            sys.exit(1)

        yield page, find_bad_lang_tags(
            page["revisions"][0]["slots"]["main"]["content"],
            skip_unsupported_langs,
        )


def to_csv(
    tags: Iterable[Tuple[Dict[str, Any], Iterable[BadLangTag]]],
    *,
    out_file: TextIO = sys.stdout,
):
    writer = csv.writer(out_file, quoting=csv.QUOTE_ALL)
    writer.writerow(
        (
            "page_id",
            "page_title",
            "revision_id",
            "revision_timestamp",
            "lang",
            "tag",
            "start_lineno",
            "end_lineno",
            "unsupported_lang",
            "orphaned",
            "start",
            "end",
            "start_start_index",
            "start_end_index",
            "end_start_index",
            "end_end_index",
            "kind",
        )
    )

    for page, _tags in tags:
        revision = page["revisions"][0]
        row = [
            page["pageid"],
            page["title"],
            revision["revid"],
            revision["timestamp"],
        ]

        for tag in _tags:
            orphaned = True if tag.end is None else False
            unsupported = (
                True if tag.tag == "highlight" and tag.lang not in ALL_LEXERS else False
            )
            end_lineno = tag.end.lineno if tag.end is not None else None
            end_start_index = tag.end.start if tag.end is not None else None
            end_end_index = tag.end.end if tag.end is not None else None
            writer.writerow(
                row
                + [
                    tag.lang,
                    tag.tag,
                    tag.start.lineno,
                    end_lineno,
                    unsupported,
                    orphaned,
                    tag.start.text,
                    tag.end.text if tag.end else None,
                    tag.start.start,
                    tag.start.end,
                    end_start_index,
                    end_end_index,
                    tag.kind,
                ]
            )


if __name__ == "__main__":
    import argparse

    URL = "https://rosettacode.org/w/api.php"

    parser = argparse.ArgumentParser(description="Find bad lang tags on Rosetta Code.")
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--category",
        help="target a Rosetta Code category, e.g. 'Category:Programming Tasks'",
    )

    group.add_argument(
        "--namespace",
        type=int,
        help="target all pages in a Rosetta Code namespace, given as an integer",
    )

    parser.add_argument(
        "--prefix",
        default="",
        help=(
            "only look at page titles with the given prefix "
            "(prefix is ignored when targeting a category)"
        ),
    )

    parser.add_argument(
        "--skip_unsupported_langs",
        action="store_true",
        help="don't report on unsupported lang attributes (defaults: false)",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=20,
        dest="chunk_size",
        help="maximum number of pages to fetch per request (default: 20)",
    )

    parser.add_argument(
        "--page-limit",
        type=int,
        default=500,
        dest="page_limit",
        help="maximum(ish) number of pages to fetch per session (default: 500)",
    )

    parser.add_argument(
        "--url",
        default=URL,
        help=f"target MediaWiki URL (default: {URL})",
    )

    parser.add_argument(
        "--outfile",
        "-o",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="destination file (default: stdout)",
    )
    # parser.add_argument(
    #     "--debug",
    #     "-d",
    #     action="store_true",
    #     help="enable debugging output (default: false)",
    # )

    args = parser.parse_args()
    session = get_session()

    if args.namespace is not None:
        tags = ap_find_bad_lang_tags(
            session,
            url=args.url,
            prefix=args.prefix,
            namespace=args.namespace,
            chunk_size=args.chunk_size,
            page_limit=args.page_limit,
            skip_unsupported_langs=args.skip_unsupported_langs,
        )
    else:
        category = (
            args.category
            if args.category.startswith("Category:")
            else "Category:" + args.category
        )
        tags = cm_find_bad_lang_tags(
            session,
            category,
            url=args.url,
            chunk_size=args.chunk_size,
            page_limit=args.page_limit,
            skip_unsupported_langs=args.skip_unsupported_langs,
        )

    to_csv(tags, out_file=args.outfile)
