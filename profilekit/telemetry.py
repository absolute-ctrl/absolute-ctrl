"""Telemetry sources.

- GitHub stats via GraphQL (needs a token: GITHUB_TOKEN or GH_TOKEN).
- Access counter + previous-visit timestamp via Upstash Redis REST (optional).
  Reads UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN, or the KV_REST_API_URL /
  KV_REST_API_TOKEN names that Vercel's storage integration creates.
Every function fails soft: the profile must always render, even when a source is down.
"""
import json
import os
import time
import urllib.request
from collections import Counter

QUERY = """query($login:String!){ user(login:$login){
  followers{totalCount} pullRequests{totalCount}
  contributionsCollection{totalCommitContributions restrictedContributionsCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){ totalCount
    nodes{ stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}} } } } }"""


def _token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _redis_env():
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
    tok = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
    return (url.rstrip("/"), tok) if url and tok else (None, None)


def redis(*commands, timeout=2.5):
    """Run commands in one Upstash REST pipeline. Returns a list of results, or None."""
    url, tok = _redis_env()
    if not url:
        return None
    req = urllib.request.Request(url + "/pipeline", data=json.dumps(list(commands)).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        return [r.get("result") for r in json.load(urllib.request.urlopen(req, timeout=timeout))]
    except Exception:
        return None


def fetch_github(user, timeout=6):
    tok = _token()
    if not tok:
        return None
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
                                 headers={"Authorization": f"bearer {tok}", "Content-Type": "application/json",
                                          "User-Agent": "profile-telemetry"})
    u = json.load(urllib.request.urlopen(req, timeout=timeout))["data"]["user"]
    langs = Counter()
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    cc = u["contributionsCollection"]
    return {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "languages": dict(langs.most_common(12)),
    }


def github_stats(user, cache_seconds=0):
    """Fresh stats every call when cache_seconds is 0; otherwise reuse a Redis-cached copy."""
    key = f"profile:{user}:stats"
    if cache_seconds > 0:
        hit = redis(["GET", key])
        if hit and hit[0]:
            try:
                return json.loads(hit[0])
            except ValueError:
                pass
    try:
        stats = fetch_github(user)
    except Exception:
        stats = None
    if stats and cache_seconds > 0:
        redis(["SET", key, json.dumps(stats), "EX", int(cache_seconds)])
    return stats


def record_access(user, count=True):
    """Increment the access counter. Returns (total, previous_access_epoch) or (None, None)."""
    now = int(time.time())
    k_views, k_last = f"profile:{user}:views", f"profile:{user}:last"
    if count:
        res = redis(["INCR", k_views], ["GETSET", k_last, str(now)])
    else:
        res = redis(["GET", k_views], ["GET", k_last])
    if not res:
        return None, None
    total = int(res[0]) if res[0] is not None else 0
    prev = int(res[1]) if res[1] else None
    return total, prev


def collect(cfg, live, count=True):
    """Everything the telemetry section needs."""
    user = cfg["user"]
    tcfg = cfg.get("telemetry", {})
    data = {"mode": "live" if live else "static", "now": int(time.time()), "accesses": None, "previous_access": None}
    if live:
        data["accesses"], data["previous_access"] = record_access(user, count)
    data["github"] = github_stats(user, float(tcfg.get("stats_cache_seconds", 0)) if live else 0)
    return data
