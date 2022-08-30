import json
import sys

from one_page import one_page
from bot_login import login


URL = "https://rosettacode.org/w/api.php"


def main(un: str, pw: str):
    session, csrf_token = login(un, pw)
    data = one_page("User:Jgrprior")
    page = data["query"]["pages"][0]
    revision = page["revisions"][0]

    # TODO: content model and format

    params = {
        "action": "edit",
        "bot": "true",
        "minor": "true",
        "pageid": page["pageid"],
        "baserevid": revision["revid"],
        "basetimestamp": revision["timestamp"],
        "starttimestamp": data["curtimestamp"],
        "format": "json",
        "appendtext": "Hello",
        "summary": "bot test",
        "token": csrf_token,
    }

    resp = session.post(URL, data=params)
    resp.raise_for_status()
    rv = resp.json()
    with open("/tmp/res.json", "w", encoding="utf-8") as fd:
        json.dump(rv, fd, indent=4)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
