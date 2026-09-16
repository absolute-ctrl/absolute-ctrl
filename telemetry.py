"""Builds assets/telemetry.svg from live GitHub data, in the profile's 3270 phosphor style.
Runs inside GitHub Actions (needs GITHUB_TOKEN). Without a token it writes a placeholder."""
import json, os, urllib.request
from collections import Counter

USER = os.environ.get("PROFILE_USER", "absolute-ctrl")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "telemetry.svg")
BG, G, A, D = "#0A0F0A", "#33FF66", "#FFB000", "#1F7A3A"
FONT = "'IBM Plex Mono','Cascadia Mono',Consolas,'Courier New',monospace"
W, H = 880, 260

QUERY = """query($login:String!){ user(login:$login){
  followers{totalCount}
  pullRequests{totalCount}
  contributionsCollection{totalCommitContributions restrictedContributionsCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){
    totalCount
    nodes{ stargazerCount
      languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}} } } } }"""

def fetch():
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    u = json.load(urllib.request.urlopen(req))["data"]["user"]
    langs = Counter()
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    cc = u["contributionsCollection"]
    stats = [("Public repositories", u["repositories"]["totalCount"]),
             ("Stars collected", sum(r["stargazerCount"] for r in u["repositories"]["nodes"])),
             ("Commits this year", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
             ("Pull requests", u["pullRequests"]["totalCount"]),
             ("Followers", u["followers"]["totalCount"])]
    return stats, langs

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render(stats, langs):
    b = f'<text x="28" y="34" fill="{A}" font-size="15" font-weight="700">&gt; TELEMETRY</text>'
    b += f'<line x1="28" y1="46" x2="{W-28}" y2="46" stroke="{D}" stroke-dasharray="4 4"/>'
    if stats is None:
        b += f'<text x="28" y="120" fill="{G}" font-size="16">Awaiting first sync ...</text>'
        b += f'<text x="28" y="148" fill="{D}" font-size="13">// run the "telemetry" workflow in the Actions tab</text>'
    else:
        for i, (k, v) in enumerate(stats):
            y = 84 + i * 30
            dots = "." * max(3, 26 - len(k))
            b += f'<text x="28" y="{y}" fill="{G}" font-size="15">{esc(k)} {dots} <tspan fill="{A}">{v}</tspan></text>'
        total = sum(langs.values()) or 1
        b += f'<text x="470" y="84" fill="{A}" font-size="14" font-weight="700">LANGUAGE MIX</text>'
        for i, (name, size) in enumerate(langs.most_common(5)):
            y = 114 + i * 28
            pct = size / total
            blocks = max(1, round(pct * 20))
            b += f'<text x="470" y="{y}" fill="{G}" font-size="14">{esc(name[:12])}</text>'
            for j in range(20):
                b += f'<rect x="{590+j*11}" y="{y-12}" width="8" height="14" fill="{G if j < blocks else "none"}" stroke="{D}"/>'
            b += f'<text x="{W-28}" y="{y}" text-anchor="end" fill="{A}" font-size="13">{pct*100:.1f}%</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000" opacity=".28"/></pattern>
<radialGradient id="glow" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#143a1c" stop-opacity=".55"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></radialGradient></defs>
<rect width="{W}" height="{H}" rx="14" fill="{BG}"/><rect width="{W}" height="{H}" rx="14" fill="url(#glow)"/>
{b}
<rect width="{W}" height="{H}" rx="14" fill="url(#scan)"/>
<rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" rx="13" fill="none" stroke="{D}" stroke-width="3"/></svg>'''

if __name__ == "__main__":
    data = fetch() if TOKEN else (None, None)
    open(OUT, "w", encoding="utf-8").write(render(*data))
    print("telemetry.svg written")
