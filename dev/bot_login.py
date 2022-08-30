import json
import sys
import requests


URL = "https://rosettacode.org/w/api.php"

LOGIN_TOKEN_PARAMS = {
    "action": "query",
    "meta": "tokens",
    "type": "login",
    "format": "json",
}

CSRF_TOKENS_PARAMS = {
    "action": "query",
    "meta": "tokens",
    "format": "json",
}


def get_login_token(session: requests.Session) -> str:
    resp = session.get(URL, params=LOGIN_TOKEN_PARAMS)
    resp.raise_for_status()
    data = resp.json()
    return data["query"]["tokens"]["logintoken"]


def post_creds(
    session: requests.Session,
    username: str,
    password: str,
    token: str,
):
    params = {
        "action": "login",
        "lgname": username,
        "lgpassword": password,
        "lgtoken": token,
        "format": "json",
    }

    resp = session.post(URL, data=params)
    resp.raise_for_status()
    data = resp.json()
    with open("/tmp/some.json", "w", encoding="utf-8") as fd:
        json.dump(data, fd, indent=4)


def get_csrf_token(session: requests.Session) -> str:
    resp = session.get(URL, params=CSRF_TOKENS_PARAMS)
    resp.raise_for_status()
    data = resp.json()
    with open("/tmp/csrf.json", "w", encoding="utf-8") as fd:
        json.dump(data, fd, indent=4)
    return data["query"]["tokens"]["csrftoken"]


def login(session: requests.Session, un: str, pw: str):
    login_token = get_login_token(session)
    post_creds(session, un, pw, login_token)
    csrf_token = get_csrf_token(session)
    print("LOGIN OK: ", csrf_token)
    return session, csrf_token
