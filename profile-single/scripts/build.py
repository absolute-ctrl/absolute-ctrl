"""Builds profile.svg: the whole GitHub profile as one continuous retro CRT screen.
Run locally for a placeholder telemetry section, or in GitHub Actions (GITHUB_TOKEN) for live stats."""
import json, math, os, random, urllib.request
from collections import Counter

USER = os.environ.get("PROFILE_USER", "absolute-ctrl")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = os.path.join(os.path.dirname(__file__), "..", "profile.svg")

BG, G, A, D = "#0A0F0A", "#33FF66", "#FFB000", "#1F7A3A"
FONT = "'IBM Plex Mono','Cascadia Mono',Consolas,'Courier New',monospace"
W = 880
random.seed(7)  # deterministic art, so daily rebuilds only change when stats change

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------------------------------------------------------------- timing
# Each step powers on after the previous one; first is slow, each next one 22% faster.
ORDER = ["boot", "whoami", "specs", "mission", "programs",
         "slot-a", "slot-b", "slot-c", "slot-d", "slot-e", "slot-f", "telemetry", "footer"]
BASE, RATE, FLOOR = 1.4, 0.78, 0.15
TIMES, _t = {}, 0.0
for i, n in enumerate(ORDER):
    d = max(FLOOR, BASE * RATE ** i); TIMES[n] = (_t, d); _t += d

def after(step, t):
    """Absolute time: t seconds after `step` finished powering on."""
    s, d = TIMES[step]; return s + d + t

def reveal(step, t):
    return f'<animate attributeName="opacity" from="0" to="1" begin="{after(step, t):.2f}s" dur="0.05s" fill="freeze"/>'

def cursor(step, x, y, t=0):
    return (f'<rect x="{x}" y="{y-14}" width="10" height="17" fill="{G}" opacity="0">'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" '
            f'begin="{after(step, t):.2f}s" repeatCount="indefinite"/></rect>')

def power(step, x, y, w, h):
    """CRT power-on for one region: black, a phosphor line sweeps across, then the picture fades in."""
    s, d = TIMES[step]
    return f'''<rect x="{x}" y="{y-1}" width="{w}" height="{h+2}" fill="{BG}">
<animate attributeName="opacity" from="1" to="0" begin="{s+d*.55:.2f}s" dur="{d*.45:.2f}s" fill="freeze"/></rect>
<rect x="{x}" y="{y+h/2-1:.1f}" width="{w}" height="2" fill="{G}" opacity="0">
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.6;1" begin="{s:.2f}s" dur="{d*.75:.2f}s" fill="freeze"/>
<animate attributeName="x" from="{x+w/2}" to="{x}" begin="{s:.2f}s" dur="{d*.45:.2f}s" fill="freeze"/>
<animate attributeName="width" from="0" to="{w}" begin="{s:.2f}s" dur="{d*.45:.2f}s" fill="freeze"/></rect>'''

def header(title, y=34, right=""):
    r = f'<text x="{W-28}" y="{y}" text-anchor="end" fill="{D}" font-size="14">{right}</text>' if right else ""
    return (f'<text x="28" y="{y}" fill="{A}" font-size="15" font-weight="700">&gt; {title}</text>{r}'
            f'<line x1="28" y1="{y+12}" x2="{W-28}" y2="{y+12}" stroke="{D}" stroke-dasharray="4 4"/>')

# ---------------------------------------------------------------- sections (local coords, return height, body)
def sec_boot():
    lines = [("ABSOLUTE-CTRL BIOS v2.0", "   (C) 2026  PHOSPHOR SYSTEMS"),
             ("Memory test ................ ", "640K OK"),
             ("Detecting graphics adapter . ", "OpenGL / Vulkan OK"),
             ("Probing CPU features ....... ", "SIMD, caches, pointers OK"),
             ("Mounting z/OS datasets ..... ", "READY"),
             ("Loading C runtime .......... ", "GCC UCRT64 OK")]
    b, y, t = "", 78, 0.1
    for i, (l, r) in enumerate(lines):
        lc, rc = (A, D) if i == 0 else (G, A)
        b += f'<text x="40" y="{y}" fill="{lc}" font-size="16" opacity="0">{esc(l)}<tspan fill="{rc}">{esc(r)}</tspan>{reveal("boot", t)}</text>'
        y += 26; t += 0.16
    b += f'<text x="40" y="{y+14}" fill="{G}" font-size="16" opacity="0">C:\\&gt; boot profile.sys{reveal("boot", t)}</text>'
    b += cursor("boot", 252, y + 14, t)
    b += f'''<g opacity="0">{reveal("boot", t+.3)}
<text x="{W-40}" y="118" text-anchor="end" fill="{A}" font-size="44" font-weight="700" letter-spacing="2">ABSOLUTE</text>
<text x="{W-40}" y="164" text-anchor="end" fill="{A}" font-size="44" font-weight="700" letter-spacing="2">-CTRL</text>
<text x="{W-40}" y="196" text-anchor="end" fill="{D}" font-size="14">systems + graphics programmer</text></g>'''
    return 290, b

def sec_whoami():
    who = ["Systems programmer. Graphics tinkerer.",
           "I write C close to the metal and COBOL close to the mainframe.",
           "I care about where every byte lives, how every pixel gets drawn,",
           "and what the OS is doing behind my back."]
    b = header("WHOAMI") + f'<text x="28" y="80" fill="{D}" font-size="15">C:\\&gt; <tspan fill="{G}">whoami</tspan></text>'
    for i, l in enumerate(who):
        b += f'<text x="28" y="{112+i*26}" fill="{A if i == 0 else G}" font-size="16">{esc(l)}</text>'
    return 220, b

def sec_specs():
    rows = [("C", "OpenGL, Vulkan, GLFW", "GCC (UCRT64)"), ("COBOL", "z/OS", "z/OS UNIX compiler")]
    cols = [28, 210, 520]
    b = header("SYSTEM SPECS")
    for x, h in zip(cols, ["LANGUAGE", "GRAPHICS / PLATFORM", "TOOLCHAIN"]):
        b += f'<text x="{x+14}" y="84" fill="{A}" font-size="14" font-weight="700">{h}</text>'
    bottom = 96 + len(rows) * 38
    b += f'<rect x="28" y="62" width="{W-56}" height="{bottom-62}" fill="none" stroke="{D}"/><line x1="28" y1="96" x2="{W-28}" y2="96" stroke="{D}"/>'
    for x in cols[1:]:
        b += f'<line x1="{x}" y1="62" x2="{x}" y2="{bottom}" stroke="{D}"/>'
    for i, r in enumerate(rows):
        for x, v in zip(cols, r):
            b += f'<text x="{x+14}" y="{124+i*38}" fill="{G}" font-size="16">{esc(v)}</text>'
    return 200, b

def sec_mission():
    ms = [("RENDERING", "Leveling up OpenGL, then Vulkan", 6),
          ("OS INTERNALS", "Windows, Linux, Raspberry Pi, z/OS", 4),
          ("HARDWARE", "Low-level features, memory done right", 3)]
    b = header("CURRENT MISSION")
    for i, (k, v, n) in enumerate(ms):
        y = 90 + i * 40
        b += f'<text x="28" y="{y}" fill="{A}" font-size="15" font-weight="700">{k}</text>'
        for j in range(10):
            x = 190 + j * 20
            if j < n:
                b += f'<rect x="{x}" y="{y-14}" width="14" height="16" fill="{G}" stroke="{D}" opacity="0">{reveal("mission", i*.25 + j*.05)}</rect>'
            else:
                b += f'<rect x="{x}" y="{y-14}" width="14" height="16" fill="none" stroke="{D}"/>'
        b += f'<text x="410" y="{y}" fill="{G}" font-size="16">{esc(v)}</text>'
    b += f'<text x="28" y="210" fill="{D}" font-size="13">// loading bars show where the journey is, not a skill rating</text>'
    return 230, b

# ---- cartridge art
CW, CH = 400, 290
def art_terrain():
    s, N, cx = "", 14, 200
    pts = [[(cx + (i-j)*13, 70 + (i+j)*5.3 - (18*math.sin(i*.7)*math.cos(j*.5) + 10*math.sin((i+j)*.9)))
            for j in range(N)] for i in range(N)]
    for i in range(N):
        s += '<polyline fill="none" stroke="%s" points="%s"/>' % (G, " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts[i]))
        s += '<polyline fill="none" stroke="%s" opacity=".6" points="%s"/>' % (D, " ".join(f"{pts[k][i][0]:.1f},{pts[k][i][1]:.1f}" for k in range(N)))
    return s
def art_dataset():
    s = ""
    for r in range(9):
        rec = f"{r+1:05d} CUST-{random.randint(1000,9999)} {random.randint(10,99999):>7}.{random.randint(10,99)} OK"
        s += f'<text x="34" y="{62+r*14}" fill="{G if r % 3 else A}" font-size="11">{rec}</text>'
    return s + f'<text x="34" y="182" fill="{D}" font-size="11">JOB00042 ENDED - RC=0000  9M REC/S</text>'
def art_voxels():
    def cube(x, y, c):
        return (f'<polygon points="{x},{y} {x+16},{y-8} {x+32},{y} {x+16},{y+8}" fill="{c}"/>'
                f'<polygon points="{x},{y} {x+16},{y+8} {x+16},{y+26} {x},{y+18}" fill="{D}"/>'
                f'<polygon points="{x+32},{y} {x+16},{y+8} {x+16},{y+26} {x+32},{y+18}" fill="#0f3d1c"/>')
    s = ""
    for gx, gy, h in [(0,0,1),(1,0,2),(2,0,1),(3,0,1),(0,1,1),(1,1,3),(2,1,1),(3,1,1),(0,2,1),(1,2,1),(2,2,2)]:
        for k in range(h):
            s += cube(140 + (gx-gy)*16, 108 + (gx+gy)*8 - k*18, A if k == h-1 and h > 1 else G)
    return s
def art_engine():
    boxes = [(36,70,"input"),(36,130,"scene"),(152,100,"renderer"),(272,70,"OpenGL"),(272,130,"Vulkan")]
    s = ""
    for a, c in [((128,67),(152,97)),((128,127),(152,97)),((244,97),(272,67)),((244,97),(272,127))]:
        s += f'<line x1="{a[0]}" y1="{a[1]}" x2="{c[0]}" y2="{c[1]}" stroke="{D}" stroke-width="1.5"/>'
    for x, y, t in boxes:
        s += f'<rect x="{x}" y="{y-16}" width="92" height="26" fill="#050805" stroke="{A if t == "renderer" else G}"/>'
        s += f'<text x="{x+46}" y="{y+2}" text-anchor="middle" fill="{G}" font-size="12">{t}</text>'
    return s + f'<text x="36" y="182" fill="{D}" font-size="11">frame 000001  16.6ms</text>'
def art_static():
    s = ""
    for _ in range(380):
        s += f'<rect x="{random.randint(22,CW-26)}" y="{random.randint(44,188)}" width="3" height="2" fill="{G}" opacity="{random.choice([.1,.2,.35])}"/>'
    return s + (f'<rect x="{CW/2-70}" y="102" width="140" height="30" fill="#050805" stroke="{D}"/>'
                f'<text x="{CW/2}" y="122" text-anchor="middle" fill="{D}" font-size="13">NO SIGNAL</text>')

def card(slot, title, stack, status, art):
    empty = status == "PLANNING"
    col = D if empty else A
    return f'''<path d="M10 0 H{CW-60} L{CW-10} 40 V{CH-10} Q{CW-10} {CH} {CW-20} {CH} H20 Q10 {CH} 10 {CH-10} Z" fill="#070b07" stroke="{col}" stroke-width="3"/>
<text x="24" y="30" fill="{col}" font-size="15" font-weight="700">SLOT {slot}:</text>
<text x="{CW-80}" y="30" text-anchor="end" fill="{D if empty else G}" font-size="12">[{status}]</text>
<rect x="22" y="44" width="{CW-44}" height="148" rx="6" fill="#050805" stroke="{D}"/>
<g clip-path="url(#scr-{slot})">{art}</g>
<text x="24" y="222" fill="{D if empty else G}" font-size="15" font-weight="700">{esc(title)}</text>
<text x="24" y="248" fill="{D if empty else A}" font-size="13">{esc(stack)}</text>
<rect x="24" y="266" width="{CW-48}" height="2" fill="{D}" opacity=".6"/>'''

CARDS = [("A", "3D Terrain Generation (Noise)", "C / OpenGL / GLFW", "IN DEV", art_terrain),
         ("B", "z/OS COBOL Fast Data Processing", "COBOL / z/OS emulation", "IN DEV", art_dataset),
         ("C", "Portable Minecraft Clone, Pure C", "C / OpenGL / GLFW", "IN DEV", art_voxels),
         ("D", "Generic Game Engine", "C / OpenGL / Vulkan / GLFW", "IN DEV", art_engine),
         ("E", "Slot empty", "awaiting input...", "PLANNING", art_static),
         ("F", "Slot empty", "awaiting input...", "PLANNING", art_static)]
CARD_X = [30, 450]

# ---- telemetry
QUERY = """query($login:String!){ user(login:$login){
  followers{totalCount} pullRequests{totalCount}
  contributionsCollection{totalCommitContributions restrictedContributionsCount}
  repositories(ownerAffiliations:OWNER,isFork:false,first:100,privacy:PUBLIC){ totalCount
    nodes{ stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}} } } } }"""
def fetch_stats():
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    u = json.load(urllib.request.urlopen(req))["data"]["user"]
    langs = Counter()
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    cc = u["contributionsCollection"]
    return ([("Public repositories", u["repositories"]["totalCount"]),
             ("Stars collected", sum(r["stargazerCount"] for r in u["repositories"]["nodes"])),
             ("Commits this year", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
             ("Pull requests", u["pullRequests"]["totalCount"]),
             ("Followers", u["followers"]["totalCount"])], langs)

def sec_telemetry(stats, langs):
    b = header("TELEMETRY")
    if stats is None:
        b += f'<text x="28" y="120" fill="{G}" font-size="16">Awaiting first sync ...</text>'
        b += f'<text x="28" y="148" fill="{D}" font-size="13">// run the "telemetry" workflow in the Actions tab</text>'
        return 250, b
    for i, (k, v) in enumerate(stats):
        b += f'<text x="28" y="{84+i*30}" fill="{G}" font-size="15">{esc(k)} {"." * max(3, 26-len(k))} <tspan fill="{A}">{v}</tspan></text>'
    total = sum(langs.values()) or 1
    b += f'<text x="470" y="84" fill="{A}" font-size="14" font-weight="700">LANGUAGE MIX</text>'
    for i, (name, size) in enumerate(langs.most_common(5)):
        y, pct = 114 + i*28, size / total
        blocks = max(1, round(pct * 20))
        b += f'<text x="470" y="{y}" fill="{G}" font-size="14">{esc(name[:12])}</text>'
        for j in range(20):
            b += f'<rect x="{590+j*11}" y="{y-12}" width="8" height="14" fill="{G if j < blocks else "none"}" stroke="{D}"/>'
        b += f'<text x="{W-28}" y="{y}" text-anchor="end" fill="{A}" font-size="13">{pct*100:.1f}%</text>'
    return 250, b

def sec_footer():
    b = (f'<text x="28" y="44" fill="{G}" font-size="18">READY.</text>'
         f'<text x="28" y="74" fill="{A}" font-size="16">PRESS ANY KEY TO CONTINUE</text>' + cursor("footer", 278, 74))
    return 100, b

# ---------------------------------------------------------------- compose
def build(stats, langs):
    body, overlays, clips, y = "", "", "", 0

    def divider(yy):
        return (f'<line x1="14" y1="{yy-2}" x2="{W-14}" y2="{yy-2}" stroke="{D}" opacity=".5"/>'
                f'<line x1="14" y1="{yy+2}" x2="{W-14}" y2="{yy+2}" stroke="{D}" opacity=".5"/>')

    for step, fn in [("boot", sec_boot), ("whoami", sec_whoami), ("specs", sec_specs), ("mission", sec_mission)]:
        h, b = fn()
        body += f'<g transform="translate(0,{y})">{b}</g>' + divider(y + h)
        overlays += power(step, 0, y, W, h)
        y += h

    h, b = 56, header("LOADED PROGRAMS", right="6 slots, 4 in use")
    body += f'<g transform="translate(0,{y})">{b}</g>'
    overlays += power("programs", 0, y, W, h)
    y += h

    for i, (slot, title, stack, status, art) in enumerate(CARDS):
        row, col = divmod(i, 2)
        cy = y + row * (CH + 20)
        cx = CARD_X[col]
        clips += f'<clipPath id="scr-{slot}"><rect x="22" y="44" width="{CW-44}" height="148" rx="6"/></clipPath>'
        body += f'<g transform="translate({cx},{cy})">{card(slot, title, stack, status, art())}</g>'
        top = y + row * (CH + 20) - 4
        bot = y + 3 * (CH + 20) + 10 if row == 2 else top + CH + 20
        overlays += power(f"slot-{slot.lower()}", col * (W // 2), top, W // 2, bot - top)
    y += 3 * (CH + 20) + 10
    body += divider(y)

    for step, fn in [("telemetry", lambda: sec_telemetry(stats, langs)), ("footer", sec_footer)]:
        h, b = fn()
        body += f'<g transform="translate(0,{y})">{b}</g>'
        if step == "telemetry":
            body += divider(y + h)
        overlays += power(step, 0, y, W, h)
        y += h

    H = y + 10
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000" opacity=".28"/></pattern>
<radialGradient id="glow" cx="50%" cy="20%" r="90%"><stop offset="0" stop-color="#143a1c" stop-opacity=".5"/><stop offset="1" stop-color="{BG}" stop-opacity="0"/></radialGradient>
<filter id="ph"><feGaussianBlur stdDeviation=".6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="screen"><rect width="{W}" height="{H}" rx="16"/></clipPath>
{clips}
</defs>
<title>absolute-ctrl: systems and graphics programmer. C with OpenGL/Vulkan/GLFW, COBOL on z/OS.</title>
<g clip-path="url(#screen)">
<rect width="{W}" height="{H}" fill="{BG}"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
<g filter="url(#ph)">{body}</g>
<rect width="{W}" height="{H}" fill="url(#scan)"/>
{overlays}
</g>
<rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" rx="15" fill="none" stroke="{D}" stroke-width="3"/>
</svg>'''

if __name__ == "__main__":
    stats, langs = fetch_stats() if TOKEN else (None, None)
    open(OUT, "w", encoding="utf-8").write(build(stats, langs))
    print("profile.svg written")
