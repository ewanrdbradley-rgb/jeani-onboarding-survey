#!/usr/bin/env python3
"""
Jeani onboarding survey collector.

Zero dependencies (Python 3.9+ stdlib). Serves the survey page and stores
responses in SQLite.

  python3 server/app.py                # serve on $PORT (default 8787)
  python3 server/app.py summary        # print a summary of responses to stdout
  python3 server/app.py export > out.csv

Endpoints
  GET  /                    survey page (survey/index.html)
  POST /api/feedback        store or update a response (upsert on response_id)
  GET  /api/summary?token=  JSON counts (needs SURVEY_ADMIN_TOKEN)
  GET  /api/export.csv?token=  all responses as CSV (needs SURVEY_ADMIN_TOKEN)
  GET  /healthz             200 OK

Environment
  PORT                  default 8787
  SURVEY_DB             default <repo>/data/feedback.db
  SURVEY_ADMIN_TOKEN    required for /api/summary and /api/export.csv
  SURVEY_CORS_ORIGIN    default "*" (set to https://feedback.jeanihealth.com in prod)
"""
import csv
import hmac
import io
import json
import os
import sqlite3
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "survey"
DB_PATH = Path(os.environ.get("SURVEY_DB", ROOT / "data" / "feedback.db"))
ADMIN_TOKEN = os.environ.get("SURVEY_ADMIN_TOKEN", "")
CORS_ORIGIN = os.environ.get("SURVEY_CORS_ORIGIN", "*")
PORT = int(os.environ.get("PORT", "8787"))

MAX_BODY = 16 * 1024
LIST_FIELDS = ("use_cases", "features", "design")
TEXT_FIELDS = {"usage": 120, "use_cases_other": 120, "improve": 1000, "uid": 128,
               "source": 64, "user_agent": 300, "page": 300}
RATE_LIMIT = (30, 60)  # 30 requests per 60 s per IP

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
  response_id     TEXT PRIMARY KEY,
  uid             TEXT,
  source          TEXT,
  rating          INTEGER,
  use_cases       TEXT,   -- JSON list
  use_cases_other TEXT,
  features        TEXT,   -- JSON list
  usage           TEXT,
  design          TEXT,   -- JSON list
  improve         TEXT,
  contact_ok      INTEGER NOT NULL DEFAULT 0,
  partial         INTEGER NOT NULL DEFAULT 1,
  user_agent      TEXT,
  page            TEXT,
  ip              TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_responses_created ON responses(created_at);
"""

_db_lock = threading.Lock()
_hits = {}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def clean(payload):
    """Validate and normalise an incoming JSON body. Returns dict or raises ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("body must be an object")
    rid = payload.get("response_id")
    if not isinstance(rid, str) or not (8 <= len(rid) <= 64) or not rid.isalnum():
        raise ValueError("bad response_id")
    out = {"response_id": rid}

    rating = payload.get("rating")
    if rating is not None:
        if not isinstance(rating, int) or not (1 <= rating <= 5):
            raise ValueError("rating must be 1-5")
    out["rating"] = rating

    for f in LIST_FIELDS:
        v = payload.get(f) or []
        if not isinstance(v, list) or len(v) > 20 or any(not isinstance(x, str) or len(x) > 120 for x in v):
            raise ValueError("bad list %s" % f)
        out[f] = json.dumps(v)

    for f, limit in TEXT_FIELDS.items():
        v = payload.get(f)
        if v is None:
            out[f] = None
            continue
        if not isinstance(v, str):
            raise ValueError("bad text %s" % f)
        out[f] = v.strip()[:limit] or None

    out["contact_ok"] = 1 if payload.get("contact_ok") else 0
    out["partial"] = 1 if payload.get("partial") else 0
    return out


def upsert(row, ip):
    ts = now_iso()
    row = dict(row, ip=ip, created_at=ts, updated_at=ts)
    cols = list(row.keys())
    updates = ", ".join("%s=excluded.%s" % (c, c) for c in cols if c not in ("response_id", "created_at"))
    sql = "INSERT INTO responses (%s) VALUES (%s) ON CONFLICT(response_id) DO UPDATE SET %s" % (
        ", ".join(cols), ", ".join("?" * len(cols)), updates)
    with _db_lock:
        conn = db()
        try:
            # Never let a late "partial" ping overwrite a completed submission.
            cur = conn.execute("SELECT partial FROM responses WHERE response_id=?", (row["response_id"],))
            existing = cur.fetchone()
            if existing is not None and existing["partial"] == 0 and row["partial"] == 1:
                return "kept"
            conn.execute(sql, [row[c] for c in cols])
            conn.commit()
            return "updated" if existing else "created"
        finally:
            conn.close()


def all_rows():
    conn = db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM responses ORDER BY created_at")]
    finally:
        conn.close()


def summary():
    rows = all_rows()
    complete = [r for r in rows if not r["partial"]]
    ratings = [r["rating"] for r in rows if r["rating"]]

    def top(field, subset):
        c = Counter()
        for r in subset:
            if field in LIST_FIELDS:
                c.update(json.loads(r[field] or "[]"))
            elif r[field]:
                c[r[field]] += 1
        return c.most_common()

    return {
        "responses_total": len(rows),
        "responses_complete": len(complete),
        "rating_avg": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "rating_dist": {str(k): v for k, v in sorted(Counter(ratings).items())},
        "use_cases": top("use_cases", complete),
        "features": top("features", complete),
        "usage": top("usage", complete),
        "design": top("design", complete),
        "sources": top("source", rows),
        "contact_ok": sum(r["contact_ok"] for r in complete),
        "improve": [{"rating": r["rating"], "text": r["improve"], "at": r["created_at"]}
                    for r in complete if r["improve"]],
    }


def export_csv():
    rows = all_rows()
    buf = io.StringIO()
    cols = ["created_at", "updated_at", "response_id", "uid", "source", "rating", "partial", "use_cases",
            "use_cases_other", "features", "usage", "design", "improve", "contact_ok", "user_agent", "page"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([" | ".join(json.loads(r[c] or "[]")) if c in LIST_FIELDS else r.get(c) for c in cols])
    return buf.getvalue()


def print_summary():
    s = summary()
    print("Jeani onboarding survey: %d responses (%d complete)" % (s["responses_total"], s["responses_complete"]))
    print("Average rating: %s   distribution: %s" % (s["rating_avg"], s["rating_dist"]))
    for key, label in (("use_cases", "Use cases"), ("features", "Useful features"),
                       ("usage", "Usage pattern"), ("design", "Design likes"), ("sources", "Sources")):
        print("\n%s" % label)
        for name, n in s[key]:
            print("  %3d  %s" % (n, name))
    print("\nWould take a call: %d" % s["contact_ok"])
    if s["improve"]:
        print("\nOne thing to improve")
        for item in s["improve"]:
            print("  [%s/5] %s" % (item["rating"] or "-", item["text"]))


def rate_limited(ip):
    limit, window = RATE_LIMIT
    now = time.time()
    hits = [t for t in _hits.get(ip, []) if now - t < window]
    hits.append(now)
    _hits[ip] = hits
    return len(hits) > limit


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC_DIR), **kw)

    # -- helpers -----------------------------------------------------------
    def client_ip(self):
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def send_json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authed(self, query):
        token = (query.get("token") or [""])[0] or self.headers.get("Authorization", "").replace("Bearer ", "")
        return bool(ADMIN_TOKEN) and hmac.compare_digest(token, ADMIN_TOKEN)

    def end_headers(self):
        # Basic hardening for the static page too.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s %s\n" % (now_iso(), self.client_ip(), fmt % args))

    # -- routes ------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/healthz":
            return self.send_json(200, {"ok": True})
        if url.path == "/api/summary":
            if not self.authed(query):
                return self.send_json(401, {"error": "unauthorized"})
            return self.send_json(200, summary())
        if url.path == "/api/export.csv":
            if not self.authed(query):
                return self.send_json(401, {"error": "unauthorized"})
            body = export_csv().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="jeani-feedback.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        if url.path.startswith("/api/"):
            return self.send_json(404, {"error": "not found"})
        # Static survey page. Query strings are ignored by the file server.
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/feedback":
            return self.send_json(404, {"error": "not found"})
        ip = self.client_ip()
        if rate_limited(ip):
            return self.send_json(429, {"error": "slow down"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self.send_json(413, {"error": "bad length"})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            row = clean(data)
        except (ValueError, UnicodeDecodeError) as e:
            return self.send_json(400, {"error": str(e)})
        result = upsert(row, ip)
        return self.send_json(200, {"ok": True, "result": result})


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "summary":
        return print_summary()
    if cmd == "export":
        return sys.stdout.write(export_csv())
    if cmd != "serve":
        sys.exit(__doc__)
    if not ADMIN_TOKEN:
        sys.stderr.write("warning: SURVEY_ADMIN_TOKEN not set; /api/summary and /api/export.csv are disabled\n")
    db().close()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stderr.write("jeani survey collector on http://0.0.0.0:%d  db=%s\n" % (PORT, DB_PATH))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
