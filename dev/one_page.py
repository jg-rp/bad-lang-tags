import json
import requests

URL = "https://rosettacode.org/w/api.php"

PARAMS = {
    "action": "query",
    "prop": "revisions",
    # "titles": "API|Main Page",
    "rvprop": "timestamp|ids",
    "rvslots": "main",
    "formatversion": "2",
    "format": "json",
    "curtimestamp": "true",
}


def one_page(titles: str):
    resp = requests.get(URL, params={**PARAMS, "titles": titles})
    resp.raise_for_status()
    return resp.json()


def main():
    data = one_page("User:Jgrprior")
    with open("/tmp/other.json", "w", encoding="utf-8") as fd:
        json.dump(data, fd, indent=4)


if __name__ == "__main__":
    main()
