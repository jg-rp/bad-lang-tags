import json
import logging
import requests

from typing import Tuple


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
    "curtimestamp": "true",
}


def get_login_token(session: requests.Session, url: str) -> str:
    resp = session.get(url, params=LOGIN_TOKEN_PARAMS)
    resp.raise_for_status()
    data = resp.json()
    return data["query"]["tokens"]["logintoken"]


def post_creds(
    session: requests.Session,
    url: str,
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

    resp = session.post(url, data=params)
    resp.raise_for_status()
    data = resp.json()
    with open("/tmp/some.json", "w", encoding="utf-8") as fd:
        json.dump(data, fd, indent=4)


def get_csrf_token(session: requests.Session, url: str) -> Tuple[str, str]:
    resp = session.get(url, params=CSRF_TOKENS_PARAMS)
    resp.raise_for_status()
    data = resp.json()
    with open("/tmp/csrf.json", "w", encoding="utf-8") as fd:
        json.dump(data, fd, indent=4)
    return (data["query"]["tokens"]["csrftoken"], data["curtimestamp"])


def login(session: requests.Session, url: str, un: str, pw: str):
    login_token = get_login_token(session, url)
    post_creds(session, url, un, pw, login_token)
    csrf_token, curtimestamp = get_csrf_token(session, url)
    logging.debug("LOGIN OK: %s", csrf_token)
    return session, csrf_token, curtimestamp
