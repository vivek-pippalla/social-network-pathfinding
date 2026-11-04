import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = (ROOT / "app/static/js/api.js").read_text(encoding="utf-8")
OPENAPI = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))
ROUTES = dict(re.findall(r"^\s{2}(\w+): \"([^\"]+)\",?$", API_SOURCE, re.MULTILINE))


def test_frontend_route_templates_exist_in_openapi():
    assert ROUTES, "No frontend route templates were found in api.js"
    for name, template in ROUTES.items():
        assert template in OPENAPI["paths"], f"{name} uses undocumented path {template}"


def test_frontend_http_methods_exist_in_openapi():
    methods = {
        "register": {"post"},
        "login": {"post"},
        "me": {"get", "put"},
        "user": {"get"},
        "search": {"get"},
        "friends": {"get"},
        "friend": {"post", "delete"},
        "mutual": {"get"},
        "path": {"get"},
        "mySuggestions": {"get"},
        "suggestions": {"get"},
    }
    assert ROUTES.keys() == methods.keys()
    for name, verbs in methods.items():
        path = ROUTES[name]
        assert verbs <= OPENAPI["paths"][path].keys(), (
            f"{name}: {verbs} missing on {path}"
        )


def test_only_api_client_calls_fetch_and_dynamic_markup_is_not_used():
    javascript = list((ROOT / "app/static/js").rglob("*.js"))
    fetch_callers = [
        path.relative_to(ROOT).as_posix()
        for path in javascript
        if re.search(r"\bfetch\s*\(", path.read_text(encoding="utf-8"))
    ]
    assert fetch_callers == ["app/static/js/api.js"]
    for path in javascript:
        source = path.read_text(encoding="utf-8")
        assert ".innerHTML" not in source
        assert "insertAdjacentHTML" not in source


def test_frontend_inputs_are_labelled_and_status_is_live():
    class AccessibilityMarkup(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inputs = set()
            self.labels = set()
            self.live_regions = 0

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "input" and attributes.get("id"):
                self.inputs.add(attributes["id"])
            if tag == "label" and attributes.get("for"):
                self.labels.add(attributes["for"])
            if attributes.get("aria-live") in {"polite", "assertive"}:
                self.live_regions += 1

    markup = AccessibilityMarkup()
    markup.feed((ROOT / "app/static/index.html").read_text(encoding="utf-8"))
    assert markup.inputs <= markup.labels
    assert markup.inputs
    assert markup.live_regions >= 1
    styles = (ROOT / "app/static/css/app.css").read_text(encoding="utf-8")
    assert "@media(max-width:" in styles
    assert "focus-visible" in styles
