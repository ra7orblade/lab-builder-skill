#!/usr/bin/env python3
"""labkit - build a lab folder from a vendor-neutral topology.yaml (see references/topology-and-configs.md).

Most runs need only:   labkit.py build LAB_DIR [--pdf]
which does, in order: initial configs -> validate -> final/checkpoint configs -> ticket configs ->
diagram + addressing table -> CML files -> expand guide/answer-key markers -> lint -> (PDFs + preview).
It prints a short summary only.

Subcommands (all also run by build)
  configs  LAB      generate initial-configs/ from topology.yaml + assets/platforms/<profile>.yaml
  assemble LAB      final-configs + checkpoints from solutions/deltas/<dev>.part<N>.<ext>
  tickets  LAB      troubleshooting/ticket-N/ from solutions/tickets/ticket-N/<dev>.delta (+ CML files)
  expand   FILE.md  fill <!-- @... --> markers in place (see expand_text)
  validate TOPO     names, links, subnets, duplicate IPs, addresses present in initial configs
  table    TOPO     Markdown addressing table (--links adds a link table)
  svg      TOPO OUT.svg
  cml      TOPO OUT.{yaml,json}  CML topology (schema 0.2.2); JSON is what an MCP import tool takes
  lint     GUIDE.md [--lab DIR]  hint refs, images, answer boxes, solution leaks, placeholders, time budget
  lookup   LAB REF  coaching: one step (3.2), Part (3), ticket (t1) or challenge, with its hints and answer key

Standard library + PyYAML (JSON topology files work without PyYAML).
"""
import argparse
import ipaddress
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROLES = {"router", "l3switch", "switch", "host", "server", "firewall", "cloud", "hub", "wan"}

# --------------------------------------------------------------------------- loading


def load_topology(path):
    path = Path(path)
    text = path.read_text()
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError:
            sys.exit("PyYAML is not installed - install it or save the topology as .json")
        data = yaml.safe_load(text)
    data.setdefault("lab", {})
    data.setdefault("nodes", [])
    data.setdefault("links", [])
    data.setdefault("zones", [])
    for n in data["nodes"]:
        n.setdefault("role", "router")
        n.setdefault("interfaces", [])
        for i in n["interfaces"]:
            for fam in ("ipv4", "ipv6"):
                v = i.get(fam)
                i[fam] = [] if v in (None, "") else (v if isinstance(v, list) else [v])
    data["links"] = [normalise_link(l) for l in data["links"]]
    data["_dir"] = path.parent
    return data


def normalise_link(l):
    if isinstance(l, (list, tuple)):
        l = {"a": l[0], "b": l[1]}
    for end in ("a", "b"):
        node, _, ifname = str(l[end]).partition(":")
        l[end + "_node"], l[end + "_if"] = node.strip(), ifname.strip()
    return l


def node_map(t):
    return {n["name"]: n for n in t["nodes"]}


def iface(t, node, ifname):
    for i in node_map(t).get(node, {}).get("interfaces", []):
        if i["name"].lower() == ifname.lower():
            return i
    return None


def config_path(t, n):
    root = t["_dir"]
    if n.get("config"):
        return (root / n["config"]).resolve()
    for cand in (root / "initial-configs", root.parent / "initial-configs"):
        for ext in (".cfg", ".sh", ".txt", ".conf"):
            p = cand / f"{n['name']}{ext}"
            if p.exists():
                return p
    return None


def addr(s):
    """'10.0.0.1/24' -> IPv4Interface; strips trailing words like 'link-local'."""
    return ipaddress.ip_interface(s.split()[0])


# --------------------------------------------------------------------------- validate


def cmd_validate(a):
    t = load_topology(a.topology)
    errors, warns = [], []
    names = [n["name"] for n in t["nodes"]]
    for dup in {x for x in names if names.count(x) > 1}:
        errors.append(f"duplicate node name {dup}")
    seen_ip = {}
    for n in t["nodes"]:
        if n["role"] not in ROLES:
            errors.append(f"{n['name']}: unknown role '{n['role']}' (use one of {sorted(ROLES)})")
        ifn = [i["name"].lower() for i in n["interfaces"]]
        for dup in {x for x in ifn if ifn.count(x) > 1}:
            errors.append(f"{n['name']}: duplicate interface {dup}")
        for i in n["interfaces"]:
            for s in i["ipv4"] + i["ipv6"]:
                try:
                    ip = addr(s)
                except ValueError as e:
                    errors.append(f"{n['name']} {i['name']}: bad address {s!r} ({e})")
                    continue
                if ip.ip.is_link_local:
                    continue
                key = str(ip.ip)
                if key in seen_ip and not i.get("shared"):
                    errors.append(f"{n['name']} {i['name']}: {key} already used on {seen_ip[key]}")
                seen_ip[key] = f"{n['name']} {i['name']}"
                net = ip.network
                if ip.version == 4 and net.prefixlen < 31 and ip.ip in (net.network_address, net.broadcast_address):
                    errors.append(f"{n['name']} {i['name']}: {s} is the network/broadcast address")
        cfg = config_path(t, n)
        if n["role"] in {"cloud", "hub", "wan"}:
            continue
        if not cfg or not cfg.exists():
            warns.append(f"{n['name']}: no initial config found")
            continue
        text = cfg.read_text().lower()
        for i in n["interfaces"]:
            if i.get("configured_in_lab"):
                continue
            for s in i["ipv4"]:
                if str(addr(s).ip) not in text:
                    warns.append(f"{n['name']} {i['name']}: {s} not found in {cfg.name} "
                                 "(set configured_in_lab: true if the learner configures it)")
            for s in i["ipv6"]:
                ip = addr(s).ip
                found = any(str(ip) == str(ipaddress.ip_address(tok)) for tok in
                            re.findall(r"[0-9a-f:]*:[0-9a-f:]+", text) if _is_ip(tok))
                if not found:
                    warns.append(f"{n['name']} {i['name']}: {s} not found in {cfg.name}")
    used = {}
    for l in t["links"]:
        for end in ("a", "b"):
            nd, ifn = l[end + "_node"], l[end + "_if"]
            if nd not in node_map(t):
                errors.append(f"link {l['a']} - {l['b']}: unknown node {nd}")
                continue
            if node_map(t)[nd]["role"] in {"cloud", "hub", "wan"} and not ifn:
                continue
            if not iface(t, nd, ifn):
                errors.append(f"link {l['a']} - {l['b']}: {nd} has no interface '{ifn}'")
                continue
            k = (nd, ifn.lower())
            if k in used and node_map(t)[nd]["role"] not in {"hub", "cloud", "wan"}:
                errors.append(f"{nd} {ifn} used by two links")
            used[k] = True
        ia, ib = iface(t, l["a_node"], l["a_if"]), iface(t, l["b_node"], l["b_if"])
        if ia and ib:
            for fam in ("ipv4", "ipv6"):
                na = {addr(s).network for s in ia[fam] if not addr(s).ip.is_link_local}
                nb = {addr(s).network for s in ib[fam] if not addr(s).ip.is_link_local}
                if na and nb and not (na & nb):
                    errors.append(f"link {l['a']} - {l['b']}: {fam} subnets differ {sorted(map(str, na))} "
                                  f"vs {sorted(map(str, nb))}")
    for z in t["zones"]:
        for nd in z.get("nodes", []):
            if nd not in node_map(t):
                errors.append(f"zone {z.get('name')}: unknown node {nd}")
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(t['nodes'])} nodes, {len(t['links'])} links: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0


def _is_ip(tok):
    try:
        ipaddress.ip_address(tok)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- table


def cmd_table(a):
    t = load_topology(a.topology)
    rows = []
    for n in t["nodes"]:
        for i in n["interfaces"]:
            if not (i["ipv4"] or i["ipv6"] or getattr(a, "all", False)):
                continue  # switch ports and unused interfaces: keep the table short
            v4 = "<br>".join(i["ipv4"])
            gua = [s for s in i["ipv6"] if not addr(s).ip.is_link_local]
            ll = [s.split()[0] for s in i["ipv6"] if addr(s).ip.is_link_local]
            rows.append([n["name"], i["name"], v4, "<br>".join(gua), "<br>".join(ll), i.get("description", "")])
    if not rows:
        return 0
    heads = ["Device", "Interface", "IPv4 Address", "IPv6 Address", "IPv6 Link-Local", "Description"]
    keep = [c for c in range(len(heads)) if c < 2 or any(r[c] for r in rows)]
    print("| " + " | ".join(heads[c] for c in keep) + " |")
    print("|" + "|".join("---" for _ in keep) + "|")
    for r in rows:
        print("| " + " | ".join(r[c] for c in keep) + " |")
    if a.links:
        print("\n| Link | Endpoint A | Endpoint B | Notes |\n|---|---|---|---|")
        for k, l in enumerate(t["links"], 1):
            print(f"| L{k} | {l['a']} | {l['b']} | {l.get('label', '')} |")
    return 0


# --------------------------------------------------------------------------- svg

ROLE_STYLE = {
    "router": ("#1f5f99", "#ffffff"), "l3switch": ("#0f766e", "#ffffff"), "switch": ("#2c8c7a", "#ffffff"),
    "host": ("#475569", "#ffffff"), "server": ("#475569", "#ffffff"), "firewall": ("#b4372f", "#ffffff"),
    "cloud": ("#94a3b8", "#1e293b"), "hub": ("#64748b", "#ffffff"), "wan": ("#94a3b8", "#1e293b"),
}
ZONE_COLORS = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]
ABBR = [("TenGigabitEthernet", "Te"), ("FortyGigabitEthernet", "Fo"), ("GigabitEthernet", "Gi"),
        ("FastEthernet", "Fa"), ("Ethernet", "E"), ("Loopback", "Lo"), ("Port-channel", "Po"),
        ("Serial", "S"), ("Tunnel", "Tu"), ("Vlan", "Vl")]


def short_if(name):
    for long, s in ABBR:
        if name.lower().startswith(long.lower()):
            return s + name[len(long):]
    return name


def icon(role, x, y):
    fill, fg = ROLE_STYLE.get(role, ROLE_STYLE["router"])
    arrows = (f'<g stroke="{fg}" stroke-width="2.4" stroke-linecap="round" fill="none">'
              f'<path d="M{x-11},{y} h22 M{x},{y-11} v22"/>'
              f'<path d="M{x+7},{y-4} l4,4 l-4,4 M{x-7},{y-4} l-4,4 l4,4 '
              f'M{x-4},{y-7} l4,-4 l4,4 M{x-4},{y+7} l4,4 l4,-4"/></g>')
    if role == "router":
        return f'<circle cx="{x}" cy="{y}" r="24" fill="{fill}"/>' + arrows
    if role == "l3switch":
        return (f'<rect x="{x-24}" y="{y-24}" width="48" height="48" rx="6" fill="{fill}"/>' + arrows)
    if role in ("switch", "hub"):
        return (f'<rect x="{x-30}" y="{y-16}" width="60" height="32" rx="5" fill="{fill}"/>'
                f'<g stroke="{fg}" stroke-width="2.2" fill="none" stroke-linecap="round">'
                f'<path d="M{x-18},{y-6} h34 l-5,-4 M{x+18},{y+6} h-34 l5,4"/></g>')
    if role == "host":
        return (f'<rect x="{x-24}" y="{y-20}" width="48" height="32" rx="3" fill="{fill}"/>'
                f'<rect x="{x-20}" y="{y-16}" width="40" height="24" fill="#e2e8f0"/>'
                f'<rect x="{x-12}" y="{y+14}" width="24" height="5" rx="1" fill="{fill}"/>')
    if role == "server":
        return (f'<rect x="{x-17}" y="{y-25}" width="34" height="50" rx="3" fill="{fill}"/>'
                + "".join(f'<rect x="{x-12}" y="{y-20+k*12}" width="24" height="7" rx="1" fill="#e2e8f0"/>'
                          for k in range(3)))
    if role == "firewall":
        return (f'<rect x="{x-26}" y="{y-20}" width="52" height="40" rx="3" fill="{fill}"/>'
                f'<g stroke="{fg}" stroke-width="1.6"><path d="M{x-26},{y-7} h52 M{x-26},{y+7} h52 '
                f'M{x-8},{y-20} v13 M{x+10},{y-7} v14 M{x-8},{y+7} v13"/></g>')
    # cloud / wan
    return (f'<path fill="{fill}" d="M{x-30},{y+14} a14,14 0 0 1 2,-27 a18,18 0 0 1 32,-6 '
            f'a14,14 0 0 1 26,8 a12,12 0 0 1 0,25 z"/>')


def auto_layout(nodes):
    missing = [n for n in nodes if "x" not in n or "y" not in n]
    for k, n in enumerate(missing):
        ang = 2 * math.pi * k / max(1, len(missing)) - math.pi / 2
        n["x"], n["y"] = round(260 * math.cos(ang)), round(200 * math.sin(ang))


def captions(n):
    """Extra text lines under a node: explicit caption(s) plus loopback addresses."""
    extra = n.get("caption") or []
    extra = [extra] if isinstance(extra, str) else list(extra)
    if n.get("show_loopbacks", True):
        for i in n["interfaces"]:
            if LOOPBACK_RE.match(i["name"]) and i["ipv4"] + i["ipv6"]:
                extra.append(f"{short_if(i['name'])} {(i['ipv4'] + i['ipv6'])[0]}")
    return extra


def caption_count(n):
    return len(captions(n))


def side_label(x, y, px, py, gap):
    """Place a label beside a line: offset along the normal (px, py), anchored away from the line."""
    if abs(px) > 0.5:  # mostly vertical line: put text to one side
        return x + px * gap, y, "start" if px > 0 else "end"
    return x + px * gap, y + py * (gap + 2), "middle"


def cmd_svg(a):
    t = load_topology(a.topology)
    nodes = node_map(t)
    auto_layout(t["nodes"])
    xs = [n["x"] for n in t["nodes"]] or [0]
    ys = [n["y"] for n in t["nodes"]] or [0]
    pad = 110
    minx, miny = min(xs) - pad, min(ys) - pad
    w, h = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx} {miny} {w} {h}" '
           f'width="{w}" height="{h}" font-family="DejaVu Sans, Helvetica, Arial, sans-serif">',
           f'<rect x="{minx}" y="{miny}" width="{w}" height="{h}" fill="#ffffff"/>',
           '<style>.lbl{font-size:11px;fill:#0f172a;paint-order:stroke;stroke:#fff;stroke-width:4px;'
           'stroke-linejoin:round}.sub{font-size:10.5px;fill:#334155;font-style:italic}'
           '.name{font-size:14px;font-weight:700;fill:#0f172a}.lo{font-size:10.5px;fill:#334155}'
           '.zone{font-size:12px;font-weight:700}</style>']
    # zones
    for k, z in enumerate(t["zones"]):
        members = [nodes[m] for m in z.get("nodes", []) if m in nodes]
        if not members:
            continue
        c = z.get("color", ZONE_COLORS[k % len(ZONE_COLORS)])
        zp = z.get("padding", 62)
        x0, x1 = min(m["x"] for m in members) - zp, max(m["x"] for m in members) + zp
        y0, y1 = min(m["y"] for m in members) - zp, max(m["y"] for m in members) + zp + 22
        out.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" rx="18" fill="{c}" '
                   f'fill-opacity="0.06" stroke="{c}" stroke-width="1.5" stroke-dasharray="7 5"/>')
        out.append(f'<text class="zone" x="{x0+12}" y="{y0+18}" fill="{c}">{escape(z.get("name", ""))}</text>')
    # links (offset parallel links between the same pair)
    pair_count = {}
    for l in t["links"]:
        A, B = nodes.get(l["a_node"]), nodes.get(l["b_node"])
        if not A or not B:
            continue
        key = tuple(sorted((A["name"], B["name"])))
        idx = pair_count.get(key, 0)
        pair_count[key] = idx + 1
        dx, dy = B["x"] - A["x"], B["y"] - A["y"]
        ln = math.hypot(dx, dy) or 1
        px, py = -dy / ln, dx / ln
        off = (idx - 0) * 16 * (1 if idx % 2 else -1) if idx else 0
        ax, ay, bx, by = A["x"] + px * off, A["y"] + py * off, B["x"] + px * off, B["y"] + py * off
        style = l.get("style", "solid")
        dash = ' stroke-dasharray="8 6"' if style == "dashed" else ""
        colour = l.get("color", "#334155")
        out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{colour}" '
                   f'stroke-width="2"{dash}/>')
        for end, (sx, sy), (ex, ey) in (("a", (ax, ay), (bx, by)), ("b", (bx, by), (ax, ay))):
            ifn = l[end + "_if"]
            if not ifn:
                continue
            owner = nodes[l[end + "_node"]]
            # links leaving a node downwards must clear its name + caption lines
            below = (ey - sy) > abs(ex - sx)
            dist = 70 + 13 * caption_count(owner) if below else 50
            f = min(0.45, dist / ln)
            lx, ly, anchor = side_label(sx + (ex - sx) * f, sy + (ey - sy) * f, px, py, 8)
            out.append(f'<text class="lbl" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">'
                       f'{escape(short_if(ifn))}</text>')
        label = l.get("label")
        if label is None:
            nets = []
            ia, ib = iface(t, l["a_node"], l["a_if"]), iface(t, l["b_node"], l["b_if"])
            for i in (ia, ib):
                for s in (i or {}).get("ipv4", []) + (i or {}).get("ipv6", []):
                    ip = addr(s)
                    if not ip.ip.is_link_local and str(ip.network) not in nets:
                        nets.append(str(ip.network))
            label = "\n".join(nets)
        parts = str(label).splitlines()
        mx, my, anchor = side_label((ax + bx) / 2, (ay + by) / 2, -px, -py, 10 + 6 * (len(parts) - 1))
        for k, part in enumerate(parts):
            out.append(f'<text class="lbl sub" x="{mx:.1f}" y="{my + 4 + (k - (len(parts) - 1) / 2) * 13:.1f}" '
                       f'text-anchor="{anchor}">{escape(part)}</text>')
    # nodes on top
    for n in t["nodes"]:
        x, y = n["x"], n["y"]
        out.append(icon(n["role"], x, y))
        out.append(f'<text class="name lbl" x="{x}" y="{y + 42}" text-anchor="middle">{escape(n["name"])}</text>')
        for k, line in enumerate(captions(n)):
            out.append(f'<text class="lo lbl" x="{x}" y="{y + 57 + k * 13}" text-anchor="middle">'
                       f'{escape(line)}</text>')
    out.append("</svg>")
    Path(a.out).write_text("\n".join(out))
    print(f"wrote {a.out}")
    return 0


# --------------------------------------------------------------------------- cml

# Interface naming per CML node definition, by slot. Verify against your server's
# node definitions (Tools > Node and Image Definitions) - releases differ.
CML_IFACES = {
    "iosv": lambda s: f"GigabitEthernet0/{s}",
    "iosvl2": lambda s: f"GigabitEthernet{s // 4}/{s % 4}",
    "iol-xe": lambda s: f"Ethernet{s // 4}/{s % 4}",
    "ioll2-xe": lambda s: f"Ethernet{s // 4}/{s % 4}",
    "csr1000v": lambda s: f"GigabitEthernet{s + 1}",
    "cat8000v": lambda s: f"GigabitEthernet{s + 1}",
    "asav": lambda s: "Management0/0" if s == 0 else f"GigabitEthernet0/{s - 1}",
    "nxosv9000": lambda s: "mgmt0" if s == 0 else f"Ethernet1/{s}",
    "alpine": lambda s: f"eth{s}", "ubuntu": lambda s: f"eth{s}", "desktop": lambda s: f"eth{s}",
    "server": lambda s: f"eth{s}", "trex": lambda s: f"eth{s}", "wan_emulator": lambda s: f"eth{s}",
    "unmanaged_switch": lambda s: f"port{s}",
    "external_connector": lambda s: "port",
}
CML_DEFAULT_DEF = {"router": "iol-xe", "l3switch": "ioll2-xe", "switch": "ioll2-xe", "host": "alpine",
                   "server": "ubuntu", "firewall": "asav", "cloud": "external_connector",
                   "hub": "unmanaged_switch", "wan": "unmanaged_switch"}
LOOPBACK_RE = re.compile(r"^(loopback\s*\d+|lo\d*)$", re.I)


def norm_if(s):
    return re.sub(r"\s+", "", s).lower()


def find_slot(defn, ifname, explicit, nodedefs=None):
    if explicit is not None:
        return int(explicit)
    names = (nodedefs or {}).get(defn)
    if names:  # authoritative list from the server (get_node_definition_detail -> device.interfaces.physical)
        for s, nm in enumerate(names):
            if norm_if(nm) == norm_if(ifname):
                return s
        return None
    fn = CML_IFACES.get(defn)
    if not fn:
        return None
    for s in range(64):
        if norm_if(fn(s)) == norm_if(ifname):
            return s
    return None


CML_LIMITS = {"title": 64, "description": 4096, "notes": 32768}


def to_yaml(obj, indent=0):
    """Minimal YAML emitter (block scalars for multi-line strings) - avoids a PyYAML dependency."""
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        out = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:\n{to_yaml(v, indent + 1)}")
            else:
                out.append(f"{pad}{k}: {scalar(v, indent + 1)}")
        return "\n".join(out)
    if isinstance(obj, list):
        if not obj:
            return "[]"
        out = []
        for item in obj:
            body = to_yaml(item, indent + 1) if isinstance(item, (dict, list)) else pad + "  " + scalar(item, indent + 1)
            out.append(f"{pad}- " + body.lstrip())
        return "\n".join(out)
    return pad + scalar(obj, indent)


def scalar(v, indent):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (dict, list)):
        return "{}" if isinstance(v, dict) else "[]"
    v = str(v)
    if "\n" in v:
        pad = "  " * (indent + 1)
        keep = "|" if v.endswith("\n") and not v.endswith("\n\n") else "|-"
        return keep + "\n" + "\n".join(pad + ln if ln.strip() else "" for ln in v.rstrip("\n").splitlines())
    return json.dumps(v)  # JSON strings are valid YAML scalars


COMMENT_LINE = re.compile(r"^(!( .*|=+)?|# .*|#=+)$")  # bare '#' is kept: it can close a banner


def mcp_json(topo):
    """JSON for an MCP import tool. The agent echoes every character as tool-call tokens, so: no
    indentation, one node or link per line, and no comment-only lines in the embedded configs
    (the YAML import file keeps them for people)."""
    for n in topo["nodes"]:
        if n["configuration"]:
            n["configuration"] = "\n".join(l for l in n["configuration"].splitlines()
                                           if not COMMENT_LINE.match(l.strip())) + "\n"
    dump = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)
    rows = lambda key: ",\n".join(dump(x) for x in topo[key])
    return ('{"lab":' + dump(topo["lab"]) + ',\n"nodes":[\n' + rows("nodes") + '],\n"links":[\n' + rows("links")
            + '],\n"annotations":[\n' + rows("annotations") + "]}\n")


def cmd_cml(a):
    t = load_topology(a.topology)
    nodedefs = {}
    for src in (ASSETS / "cml-nodedefs.json", t["_dir"] / "cml-nodedefs.json",
                Path(a.nodedefs) if getattr(a, "nodedefs", None) else None):
        if src and src.exists():
            nodedefs.update({k: v for k, v in json.loads(src.read_text()).items() if not k.startswith("_")})
    problems, iface_ids, nodes = [], {}, []
    auto_layout(t["nodes"])
    for k, n in enumerate(t["nodes"]):
        img = n.get("image", {}) if isinstance(n.get("image"), dict) else {}
        defn = img.get("cml") or CML_DEFAULT_DEF.get(n["role"], "iol-xe")
        cfg = config_path(t, n)
        # ticket / checkpoint variants: first match wins, initial config otherwise
        for d in (getattr(a, "configs_dir", None), getattr(a, "fallback_dir", None)):
            alt = find_cfg(Path(d), n["name"]) if d else None
            if alt:
                cfg = alt
                break
        conf = cfg.read_text() if cfg and cfg.exists() else ""
        if not conf and n["role"] not in {"cloud", "hub", "wan"}:
            problems.append(f"{n['name']}: no initial config - node will boot empty")
        used = {}
        for i in n["interfaces"]:
            if LOOPBACK_RE.match(i["name"]) and i.get("slot") is None:
                continue  # loopbacks live in the config, not as CML interfaces
            slot = find_slot(defn, i["name"], i.get("slot"), nodedefs)
            if slot is None:
                problems.append(f"cannot map {n['name']} {i['name']} to a slot on '{defn}' - "
                                "pass --nodedefs or add 'slot:'")
                continue
            used[slot] = i["name"]
        names = nodedefs.get(defn)
        fn = (lambda s: names[s]) if names else CML_IFACES.get(defn, lambda s: f"slot{s}")
        ifaces = []
        for s in range(max(used) + 1 if used else 0):  # CML wants contiguous slots
            label = used.get(s, fn(s))
            ifaces.append({"id": f"i{s}", "label": label, "slot": s, "type": "physical"})
            iface_ids[(n["name"], norm_if(label))] = (f"n{k}", f"i{s}")
        node = {"id": f"n{k}", "label": n["name"], "node_definition": defn,
                "x": int(n["x"]), "y": int(n["y"]), "tags": list(n.get("tags", [])),
                "configuration": conf or None, "interfaces": ifaces}
        if img.get("cml_image"):
            node["image_definition"] = img["cml_image"]
        nodes.append(node)
    links = []
    nmap = node_map(t)
    for k, l in enumerate(t["links"]):
        ends = []
        for end in ("a", "b"):
            nd, ifn = l[end + "_node"], l[end + "_if"]
            if ifn and (nd, norm_if(ifn)) in iface_ids:
                ends.append(iface_ids[(nd, norm_if(ifn))])
            elif not ifn and nmap[nd]["role"] in {"cloud", "hub", "wan"}:
                cands = [v for kk, v in iface_ids.items() if kk[0] == nd]
                if cands:
                    ends.append(cands[0])
            if len(ends) < (1 if end == "a" else 2):
                problems.append(f"cannot map link {l['a']} - {l['b']}: no CML interface for {nd}:{ifn}")
                break
        if len(ends) == 2:
            links.append({"id": f"l{k}", "n1": ends[0][0], "i1": ends[0][1], "n2": ends[1][0],
                          "i2": ends[1][1], "label": f"{l['a']} <-> {l['b']}"[:128]})
    annotations = []
    for k, z in enumerate(t["zones"]):  # zones -> dashed rectangles + labels on the CML canvas
        members = [nmap[m] for m in z.get("nodes", []) if m in nmap]
        if not members:
            continue
        c = z.get("color", ZONE_COLORS[k % len(ZONE_COLORS)])
        pad = z.get("padding", 70)
        x0, y0 = min(m["x"] for m in members) - pad, min(m["y"] for m in members) - pad
        x1, y1 = max(m["x"] for m in members) + pad, max(m["y"] for m in members) + pad
        annotations.append({"type": "rectangle", "x1": x0, "y1": y0, "x2": x1 - x0, "y2": y1 - y0,
                            "border_color": c, "border_style": "dashed", "color": c + "14",
                            "thickness": 2, "border_radius": 12, "z_index": -1})
        annotations.append({"type": "text", "x1": x0 + 10, "y1": y0 + 8, "text_content": z.get("name", ""),
                            "text_bold": True, "text_size": 14, "text_unit": "pt", "color": c,
                            "border_color": "#00000000", "z_index": 1})
    lab = {"title": a.title or t["lab"].get("title", "Lab"),
           "description": t["lab"].get("description", ""),
           "notes": t["lab"].get("notes", "Initial lab - chapter features intentionally unconfigured."),
           "version": "0.2.2"}
    for key, limit in CML_LIMITS.items():
        if len(lab[key]) > limit:
            problems.append(f"cannot use lab {key}: {len(lab[key])} characters, CML allows {limit}")
    topo = {"lab": lab, "nodes": nodes, "links": links, "annotations": annotations}
    fmt = a.format or ("json" if a.out.endswith(".json") else "yaml")
    Path(a.out).write_text(mcp_json(topo) if fmt == "json" else to_yaml(topo) + "\n")
    for p in problems:
        if not getattr(a, "quiet", False) or p.startswith("cannot"):
            print("WARN ", p)
    if not getattr(a, "quiet", False):
        print(f"wrote {a.out} ({fmt}, {len(nodes)} nodes, {len(links)} links, {len(annotations) // 2} zones)")
    return 1 if any(p.startswith("cannot") for p in problems) else 0


# --------------------------------------------------------------------------- lint

PROMPT_RE = re.compile(r"^\s*[\w.\-/]+(\([^)]*\))?\s*[#>$%]\s*")
TRIVIAL = re.compile(r"^(!.*|#.*|exit|end|quit|top|commit|write( memory)?|copy run.*|"
                     r"conf(igure)?( t(erminal)?)?|interface \S+|no shut(down)?|shut(down)?|"
                     r"exit-address-family|\{|\}|)$", re.I)


def norm_line(s):
    s = PROMPT_RE.sub("", s) if PROMPT_RE.match(s) and re.search(r"[#>$%]\s", s) else s
    return re.sub(r"\s+", " ", s).strip().lower()


def config_lines(folder):
    out = set()
    for p in sorted(Path(folder).glob("**/*")):
        if p.is_file() and p.suffix in (".cfg", ".txt", ".conf", ".py", ".yaml", ".yml", ".json"):
            for ln in p.read_text(errors="ignore").splitlines():
                n = norm_line(ln)
                if n and not TRIVIAL.match(n) and len(n) > 5:
                    out.add(n)
    return out


# --------------------------------------------------------------------------- time budget (references/depth-and-time.md)

DEPTHS = {"low": ("Low", 60, 70), "medium": ("Medium", 90, 110), "high": ("High", 180, 210), "max": ("Max", 240, 240)}
TIME_RE = re.compile(r"\((optional,\s*)?(\d+)\s*min\)\s*$", re.I)


def lab_depth(lab):
    """lab.depth from topology.yaml (low|medium|high|max or 1-4); None for labs made before depth levels."""
    f = topo_file(lab)
    if not f.exists():
        return None
    d = str(load_topology(f)["lab"].get("depth") or "").strip().lower()
    return {"1": "low", "2": "medium", "3": "high", "4": "max"}.get(d, d) or None


def time_sections(text):
    """[(heading, minutes or None, optional, body)] for each '## ' section before the appendices."""
    out, chunks = [], re.split(r"^(## .*)$", text, flags=re.M)
    for k in range(1, len(chunks), 2):
        head, body = chunks[k][3:].strip(), chunks[k + 1]
        if head.lower().startswith("appendix"):
            break
        m = TIME_RE.search(head)
        out.append((head, int(m[2]) if m else None, bool(m and m[1]) or "optional" in head.lower(), body))
    return out


def content_minutes(head, body):
    """Lower-bound estimate from what a section asks the learner to do (costs from depth-and-time.md)."""
    mins = len(re.findall(r"^### Step", body, re.M)) * (3 if head.startswith("Part 1:") else 6)
    mins += 5 * len(re.findall(r"^>\s*\*\*Break it", body, re.M))
    mins += 12 * len(re.findall(r"^### Ticket", body, re.M))
    mins += 3 * len(re.findall(r"^\|\s*\d+\s*\|", body, re.M))  # acceptance-test rows
    if re.search(r"Readiness|Reflection", head, re.I):
        mins += 2 * len(re.findall(r"^\d+\.\s", body, re.M))
    return mins


def time_totals(text):
    secs = time_sections(text)
    req = sum(m for _, m, opt, _ in secs if m and not opt)
    extra = sum(m for _, m, opt, _ in secs if m and opt)
    floor = sum(content_minutes(h, b) for h, m, opt, b in secs if not opt)
    return secs, req, extra, floor


def fmt_minutes(m):
    h, m = divmod(m, 60)
    return f"{h} h {m} min" if h and m else f"{h} h" if h else f"{m} min"


def time_issues(text, depth):
    if depth not in DEPTHS:
        return [f"unknown lab.depth '{depth}' in topology.yaml (use low, medium, high or max)"]
    name, target, cap = DEPTHS[depth]
    secs, req, _, floor = time_totals(text)
    issues = [f"'{h[:50]}' has no time estimate: end the heading with '(N min)'"
              for h, m, _, _ in secs if m is None and re.match(r"Part \d+:", h)]
    if req > cap:
        issues.append(f"estimated time {req} min exceeds the {name} cap of {cap} min (target {target}): "
                      "apply the time savers or split the lab (references/depth-and-time.md)")
    if floor and req < 0.7 * floor:
        issues.append(f"headings add up to {req} min, but the content needs at least ~{floor} min: re-estimate honestly")
    return issues


# --------------------------------------------------------------------------- quality gates (any model)

VAGUE_RE = re.compile(r"\b(verify (that )?it works|make sure (it|that it) works|works (correctly|properly|as expected)|"
                      r"is working|everything works)\b", re.I)
MIN_TICKETS = {"low": 1, "medium": 2, "high": 2, "max": 2}
IF_RE = re.compile(r"\b(TenGigabitEthernet|GigabitEthernet|FastEthernet|Ethernet|Serial|Loopback|Tunnel|Port-channel|"
                   r"Te|Gi|Fa|Et|Se|Lo|Tu|Po)\s?(\d+(?:/\d+)*)\b")
IF_CANON = {"te": "tengigabitethernet", "gi": "gigabitethernet", "fa": "fastethernet", "et": "ethernet", "e": "ethernet",
            "se": "serial", "s": "serial", "lo": "loopback", "tu": "tunnel", "po": "port-channel"}


def canon_if(name):
    m = re.match(r"^\s*([a-z-]+)\s*([\d/.:]+)\s*$", name.lower())
    return (IF_CANON.get(m[1], m[1]) + m[2]) if m else name.lower()


def structure_issues(text, lab, depth):
    """Structural rules from the pedagogy rules card that a script can check."""
    issues = []
    for head, _, _, body in time_sections(text):
        m = re.match(r"Part (\d+):", head)
        if not m or m[1] == "1" or "### Step" not in body or re.search(r"ticket|challenge", head, re.I):
            continue
        for label, pat in (("Predict", r"Predict"), ("Question", r"(Question|Explain|Reflect)"), ("Checkpoint", r"Checkpoint")):
            if not re.search(rf"^>\s*\*\*{pat}", body, re.M):
                issues.append(f"'{head[:50]}' has no {label} callout (rules card 3-4)")
    for m in re.finditer(r"^>\s*\*\*Checkpoint:\*\*(.*)$", text, re.M):
        if VAGUE_RE.search(m[1]):
            issues.append(f"vague checkpoint, make it binary and observable: {m[1].strip()[:70]!r}")
    appendix = section(text, r"^## Appendix A.*$", 2)
    for h, body in re.findall(r"^#{3,4}\s*(H\d+\.\d+[a-z]?)\b(.*?)(?=^#|\Z)", appendix, re.M | re.S):
        missing = [str(k) for k in (1, 2, 3) if not re.search(rf"Level {k}\b", body)]
        if missing:
            issues.append(f"hint {h} lacks level(s) {', '.join(missing)}: every hint has three levels")
    key_f = lab / "solutions" / "answer-key.md"
    key = key_f.read_text() if key_f.exists() else ""
    in_guide = set(re.findall(r"^### Ticket (\d+)", text, re.M))
    in_dirs = {p.name[7:] for p in (lab / "solutions" / "tickets").glob("ticket-*") if p.is_dir()}
    for n in sorted(in_guide ^ in_dirs):
        issues.append(f"ticket {n} is " + ("in the guide but has no solutions/tickets/ticket-" + n if n in in_guide
                                          else "in solutions/tickets but not in the guide (### Ticket " + n + ")"))
    if key:
        for n in sorted(in_guide - set(re.findall(r"^### Ticket (\d+)", key, re.M))):
            issues.append(f"ticket {n} has no '### Ticket {n}' section in the answer key")
        for n in sorted(set(re.findall(r"^## Part (\d+)", text, re.M)) - set(re.findall(r"^## Part (\d+)", key, re.M)), key=int):
            issues.append(f"Part {n} has no '## Part {n}' section in the answer key")
    if depth in MIN_TICKETS:
        if len(in_guide) < MIN_TICKETS[depth]:
            issues.append(f"{len(in_guide)} ticket(s): depth {depth} needs at least {MIN_TICKETS[depth]} (depth-and-time.md §1)")
        rc = section(text, r"^## .*Readiness Check.*$", 2)
        if len(re.findall(r"^\d+\.\s", rc, re.M)) < 3:
            issues.append("the Readiness Check needs at least 3 numbered questions")
        cmap = next((p for p in (lab / "concept-map.md", lab.parent / "concept-map.md") if p.exists()), None)
        if not cmap:
            issues.append("no concept-map.md in the lab folder or its parent")
        elif not re.search(r"^## Time plan", cmap.read_text(), re.M):
            issues.append(f"{cmap.name} has no '## Time plan' section (depth-and-time.md §6)")
    return issues


def lab_values(lab):
    """Addresses, networks and interface names the lab actually uses: topology plus every config."""
    t = load_topology(topo_file(lab))
    ips, nets, ifs = set(), [], set()
    for n in t["nodes"]:
        for i in n["interfaces"]:
            ifs.add(canon_if(i["name"]))
            for s in i["ipv4"] + i["ipv6"]:
                ip = addr(s)
                ips.add(str(ip.ip))
                nets.append(ip.network)
    conf = ""
    for d in ("initial-configs", "solutions", "troubleshooting"):
        for p in (lab / d).rglob("*"):
            if p.is_file() and p.suffix in (".cfg", ".delta", ".sh", ".txt", ".conf"):
                conf += p.read_text(errors="ignore").lower() + "\n"
    ifs |= {canon_if(m[1] + m[2]) for m in re.finditer(IF_RE.pattern, conf, re.I)} | \
           {canon_if(x) for x in re.findall(r"^\s*interface\s+(\S+)", conf, re.M)}
    return ips, nets, ifs, conf


def review_items(text, lab):
    """Values worth a second look: not failures (break-it steps use wrong values on purpose), but
    every one should be checked against topology.yaml and the configs."""
    if not topo_file(lab).exists():
        return []
    ips, nets, ifs, conf = lab_values(lab)
    key_f = lab / "solutions" / "answer-key.md"
    body = re.sub(r"<!-- @[^>]*-->.*?<!-- @end -->", "", text + "\n" + (key_f.read_text() if key_f.exists() else ""), flags=re.S)
    items = []
    v4 = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b", body)
    v6 = re.findall(r"(?<![\w:])[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?:/\d{1,3})?", body)
    for tok in sorted(set(v4) | {x for x in v6 if "::" in x or x.count(":") == 7}):
        try:
            ip = ipaddress.ip_interface(tok)
        except ValueError:
            continue
        a = ip.ip
        if a.is_multicast or a.is_unspecified or a.is_link_local or str(a).startswith(("255.", "0.")) \
                or str(a) in ips or str(a) in conf:
            continue
        if any(ip.network.version == n.version and (a in n or n.subnet_of(ip.network)) for n in nets):
            continue
        items.append(f"address {tok} is not in topology.yaml or any config: intended, or a typo?")
    for m in sorted({m.group(0) for m in IF_RE.finditer(body)}):
        if canon_if(m) not in ifs and "/" in m:
            items.append(f"interface {m} doesn't exist in this lab: intended (e.g. the book's name), or a typo?")
    return items


def cmd_lint(a):
    guide = Path(a.guide)
    text = guide.read_text()
    lab = Path(a.lab) if a.lab else guide.parent
    issues = []
    depth = lab_depth(lab)
    issues += structure_issues(text, lab, depth)
    for item in review_items(text, lab):
        print("CHECK", item)
    if depth:
        issues += time_issues(text, depth)
        _, req, extra, _ = time_totals(text)
        name, target, cap = DEPTHS.get(depth, (depth, 0, 0))
        print(f"TIME  {req} min" + (f" (+ {extra} min optional)" if extra else "") +
              f", depth {name}: target {target}, cap {cap}")
    # hint references vs. definitions
    refs = set(re.findall(r"\bH\d+\.\d+[a-z]?\b", re.sub(r"^#+ .*$", "", text, flags=re.M)))
    defs = set(re.findall(r"^#+\s*(H\d+\.\d+[a-z]?)\b", text, flags=re.M))
    for r in sorted(refs - defs):
        issues.append(f"hint {r} is referenced but has no '### {r}' entry in the hint appendix")
    for d in sorted(defs - refs):
        issues.append(f"hint {d} is defined but never referenced from a task")
    # images and relative links
    for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)\)", text):
        target = m.group(1).split("#")[0]
        if target and not re.match(r"^[a-z]+:", target) and not (guide.parent / target).exists():
            issues.append(f"broken link/image: {target}")
    # questions without an answer space
    lines = text.splitlines()
    for k, ln in enumerate(lines):
        if re.match(r"^>\s*\*\*(Question|Predict|Explain|Reflect)", ln):
            window = "\n".join(lines[k:k + 8])
            if 'class="answer' not in window:
                issues.append(f"line {k + 1}: '{ln.strip()[:50]}' has no answer box within 8 lines")
    for k, ln in enumerate(lines):
        if re.search(r"TODO|TBD|\{\{|lorem ipsum", ln, re.I):
            issues.append(f"line {k + 1}: unfilled placeholder: {ln.strip()[:70]!r}")
    # solution leak check
    sol, init = lab / "solutions", lab / "initial-configs"
    if sol.exists():
        secret = config_lines(sol) - (config_lines(init) if init.exists() else set())
        guide_lines = text.splitlines()
        in_code, skip, appendix = False, False, False
        for k, ln in enumerate(guide_lines):
            if re.match(r"^#+\s.*hint", ln, re.I):
                appendix = True  # hints may not leak either, keep checking but label it
            if ln.strip().startswith("```"):
                # a "<!-- leak-ok -->" line right before a fence exempts that one block
                skip = (not in_code) and k > 0 and "leak-ok" in guide_lines[k - 1]
                in_code = not in_code
                continue
            candidates = [ln] if in_code else re.findall(r"`([^`]+)`", ln)
            for c in candidates:
                n = norm_line(c)
                if not skip and n in secret:
                    where = "hint appendix" if appendix else "guide"
                    issues.append(f"line {k + 1}: solution command shown in {where}: {c.strip()!r}")
    for i in issues:
        print("LINT ", i)
    print(f"{len(issues)} issue(s)")
    return 1 if issues else 0


# --------------------------------------------------------------------------- configs / assemble / tickets

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"
GEN_MARK = "generated by labkit"
DELTA_RE = re.compile(r"^(?P<dev>.+)\.part(?P<part>\d+)\.(cfg|txt|conf|sh)$")


def find_cfg(folder, name):
    for ext in (".cfg", ".sh", ".txt", ".conf"):
        p = folder / f"{name}{ext}"
        if p.exists():
            return p
    return None


def lab_root(path):
    """Folder that contains topology/topology.yaml (or .json), searching upwards from path."""
    p = Path(path).resolve()
    for d in [p] + list(p.parents):
        for f in ("topology/topology.yaml", "topology/topology.json"):
            if (d / f).exists():
                return d
    sys.exit(f"error: no topology/topology.yaml found at or above {path}")


def topo_file(lab):
    y = Path(lab) / "topology" / "topology.yaml"
    return y if y.exists() else Path(lab) / "topology" / "topology.json"


def load_yaml(path):
    import yaml
    return yaml.safe_load(Path(path).read_text())


def platform_name(t, n):
    if n.get("platform"):
        return n["platform"]
    if n["role"] in {"cloud", "hub", "wan"}:
        return None
    if n["role"] in {"host", "server"}:
        return t["lab"].get("host_platform", "linux-host")
    return t["lab"].get("platform", "cisco-ios")


def load_profile(t, name):
    for d in (t["_dir"] / "platforms", ASSETS / "platforms"):  # a lab-local profile overrides the shipped one
        f = d / f"{name}.yaml"
        if f.exists():
            return load_yaml(f)
    sys.exit(f"error: no platform profile '{name}' (add assets/platforms/{name}.yaml)")


def linked_ifaces(t):
    return {(l[e + "_node"], l[e + "_if"].lower()) for l in t["links"] for e in ("a", "b") if l[e + "_if"]}


def render_initial(t, n, prof):
    c = prof["comment"]
    lab = t["lab"]
    bar = f"{c} " + "=" * 68
    host = n["role"] in {"host", "server"}
    inc = n.get("included") or ("hostname, addressing, default gateway" if host else
                                lab.get("included", "hostname, console settings, interface addressing"))
    head = [bar, f"{c} {lab.get('title', 'Lab')} - INITIAL configuration for {n['name']} ({GEN_MARK})",
            f"{c} Included : {inc}"]
    if not host and n.get("not_included", lab.get("not_included")):
        head.append(f"{c} NOT included (you configure these in the lab): "
                    f"{n.get('not_included', lab.get('not_included'))}")
    head.append(bar)
    v = {"name": n["name"], "gateway": n.get("gateway", ""), "gateway6": n.get("gateway6", "")}
    body = [ln.format(**v) for ln in prof.get("base", [])]
    has6 = any(i["ipv6"] for i in n["interfaces"])
    if has6 and prof.get("ipv6_global"):
        body.append(prof["ipv6_global"])
    body += n.get("extra", [])
    if prof.get("separator") is not None and body:
        body.append(prof.get("separator", ""))
    linked = linked_ifaces(t)
    indent = " " if prof["comment"] == "!" else ""
    for i in n["interfaces"]:
        iv = dict(v, ifname=i["name"], description=i.get("description", ""))
        learner = i.get("configured_in_lab")  # the learner adds the addressing: bring it up without it
        v4s, v6s = ([], []) if learner else (i["ipv4"], i["ipv6"])
        used = bool(v4s or v6s or learner or i.get("up") or (n["name"], i["name"].lower()) in linked)
        block = [prof["iface_open"].format(**iv)] if prof.get("iface_open") else []
        if i.get("description") and prof.get("iface_description"):
            block.append(prof["iface_description"].format(**iv))
        if used:
            for k, s4 in enumerate(v4s):
                ip = addr(s4)
                line = prof["iface_ipv4"].format(ip=ip.ip, mask=ip.netmask, prefix=ip.network.prefixlen, **iv)
                block.append(line + (" secondary" if k and prof["comment"] == "!" else ""))
            if not v4s and prof.get("iface_noip"):
                block += [ln.format(**iv) for ln in prof["iface_noip"]]
            for s6 in v6s:
                parts = s6.split()
                six = parts[0] + (" link-local" if "link-local" in s6 and prof["comment"] == "!" else "")
                block.append(prof["iface_ipv6"].format(ipv6=six, **iv))
            block += [indent + x for x in i.get("extra", [])]
            block += [ln.format(**iv) for ln in prof.get("iface_up", [])]
        else:
            block += [ln.format(**iv) for ln in prof.get("iface_unused", [])]
        if prof.get("iface_close"):
            block.append(prof["iface_close"])
        if prof.get("separator") is not None and prof.get("iface_open"):
            block.append(prof.get("separator", ""))
        body += [b for b in block if b != "" or prof.get("iface_open")]
    if n.get("gateway") and prof.get("gateway_v4"):
        body.append(prof["gateway_v4"].format(**v))
    if n.get("gateway6") and prof.get("gateway_v6"):
        body.append(prof["gateway_v6"].format(**v))
    if prof.get("footer"):
        body.append(prof["footer"])
    return "\n".join(head + body).rstrip() + "\n"


def cmd_configs(a):
    lab = lab_root(a.lab)
    t = load_topology(topo_file(lab))
    out = lab / "initial-configs"
    out.mkdir(exist_ok=True)
    made, kept = [], []
    for n in t["nodes"]:
        pname = platform_name(t, n)
        if not pname or n.get("config"):
            continue
        prof = load_profile(t, pname)
        f = out / f"{n['name']}{prof.get('extension', '.cfg')}"
        if f.exists() and GEN_MARK not in f.read_text(errors="ignore") and not a.force:
            kept.append(n["name"])  # hand-written: leave it alone
            continue
        f.write_text(render_initial(t, n, prof))
        made.append(n["name"])
    msg = f"configs: generated {len(made)}"
    if kept:
        msg += f", kept hand-written {', '.join(kept)} (use --force to regenerate)"
    print(msg)
    return 0


def comment_char(text):
    return "#" if text.lstrip().startswith("#") else "!"


def insert_before_footer(text, extra):
    lines = text.rstrip("\n").split("\n")
    if lines and lines[-1].strip() == "end":
        return "\n".join(lines[:-1] + [extra.rstrip("\n"), "end"]) + "\n"
    return "\n".join(lines + [extra.rstrip("\n")]) + "\n"


def relabel(text, label, state):
    c = comment_char(text)
    out = []
    for ln in text.split("\n"):
        if ln.startswith(f"{c} NOT included"):
            continue
        ln = ln.replace(" - INITIAL configuration", f" - {label} configuration").replace(f" ({GEN_MARK})", "")
        out.append(ln)
        if ln.startswith(f"{c} Included") and state:
            out.append(f"{c} State    : {state}")
    return "\n".join(out)


def read_deltas(lab):
    d = lab / "solutions" / "deltas"
    deltas = {}
    if d.exists():
        for f in sorted(d.iterdir()):
            m = DELTA_RE.match(f.name)
            if m:
                deltas.setdefault(m["dev"], {})[int(m["part"])] = f.read_text()
    return deltas


def cmd_assemble(a):
    lab = lab_root(a.lab)
    t = load_topology(topo_file(lab))
    deltas = read_deltas(lab)
    if not deltas:
        print("assemble: no solutions/deltas/<dev>.part<N>.cfg files - skipped")
        return 0
    parts = sorted({p for d in deltas.values() for p in d})
    checkpoints = t["lab"].get("checkpoints", parts[:-1])
    for n in t["nodes"]:
        init = config_path(t, n)
        if not init or not init.exists():
            continue
        base, c = init.read_text(), comment_char(init.read_text())

        def upto(limit, label, state):
            add = "".join(f"{c} ---- added in Part {p} ----\n" + deltas[n["name"]][p].rstrip("\n") + "\n"
                          for p in parts if p <= limit and p in deltas.get(n["name"], {}))
            txt = relabel(base, label, state)
            return insert_before_footer(txt, add) if add else txt

        fin = lab / "solutions" / "final-configs" / init.name
        fin.parent.mkdir(parents=True, exist_ok=True)
        fin.write_text(upto(parts[-1], "FINAL", f"end of Part {parts[-1]} - complete reference (answer key)"))
        for cp in checkpoints:
            f = lab / "solutions" / "checkpoints" / f"part-{cp}" / init.name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(upto(cp, f"PART-{cp}", f"end of Part {cp} - load to resume at Part {cp + 1}"))
    print(f"assemble: final configs + checkpoints {checkpoints} from parts {parts}")
    return 0


def cmd_tickets(a):
    lab = lab_root(a.lab)
    t = load_topology(topo_file(lab))
    src = lab / "solutions" / "tickets"
    if not src.exists():
        print("tickets: no solutions/tickets/ticket-N/<dev>.delta files - skipped")
        return 0
    final = lab / "solutions" / "final-configs"
    title = t["lab"].get("short_title") or t["lab"].get("title", "Lab")
    made = []
    for tdir in sorted(src.iterdir(), key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)]):
        if not tdir.is_dir():
            continue
        out = lab / "troubleshooting" / tdir.name
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(tdir.glob("*.delta")):
            dev = f.stem
            base = find_cfg(final, dev) or config_path(t, node_map(t).get(dev, {"name": dev}))
            if not base:
                print(f"WARN  tickets: no final/initial config for {dev}")
                continue
            label = tdir.name.upper().replace("-", " ")
            txt = relabel(base.read_text(), label, "trouble ticket - load it, do NOT read it")
            # no marker comment: the fault must not be visible in the config
            (out / base.name).write_text(insert_before_footer(txt, f.read_text()))
        name = f"{title[:50]} - {tdir.name.replace('-', ' ').title()}"[:64]
        ns = argparse.Namespace(topology=str(topo_file(lab)), out=str(lab / "topology" / f"{tdir.name}.cml.yaml"),
                                configs_dir=str(out), fallback_dir=str(final), title=name, nodedefs=None,
                                format="yaml", quiet=True)
        cmd_cml(ns)
        made.append(tdir.name)
    print(f"tickets: built {', '.join(made) or 'none'}")
    return 0


# --------------------------------------------------------------------------- expand (markers in Markdown)

DIRECTIVE_RE = re.compile(r"^<!--\s*@(?P<kind>[\w-]+)(?P<args>[^>]*?)\s*-->\s*$")


def resolve(lab, ref):
    if ref.startswith("skill:"):
        return ASSETS / ref[len("skill:"):]
    return lab / ref


def expand_text(text, lab):
    """Fill marker regions. Each marker is followed by generated content and <!-- @end -->; re-running
    replaces the region, so the file stays the single source. Markers:
      <!-- @include PATH -->            Markdown file (PATH relative to the lab root; skill:snippets/x.md for assets)
      <!-- @code PATH [lang] -->        a file as a fenced code block
      <!-- @deltas part=N -->           every solutions/deltas/<dev>.partN.* as '**dev**' + code block
      <!-- @ticket N -->                fault lines of solutions/tickets/ticket-N/*.delta (answer key)
      <!-- @table addressing -->        addressing table from topology.yaml
      <!-- @objectives -->              bullet list of this document's '## Part N: ...' headings
      <!-- @time -->                    estimated time from lab-guide.md's '(N min)' headings, plus the depth
    """
    lines = text.split("\n")
    t = load_topology(topo_file(lab))
    out, i = [], 0
    while i < len(lines):
        m = DIRECTIVE_RE.match(lines[i].strip())
        if not m or m["kind"] == "end":
            out.append(lines[i])
            i += 1
            continue
        out.append(lines[i])
        j = i + 1  # skip an existing generated region
        while j < len(lines) and not DIRECTIVE_RE.match(lines[j].strip()):
            j += 1
        if j < len(lines) and DIRECTIVE_RE.match(lines[j].strip())["kind"] == "end":
            i = j + 1
        else:
            i += 1
        out += ["", directive_content(m["kind"], m["args"].split(), lab, t, text).rstrip("\n"), "", "<!-- @end -->"]
    return "\n".join(out)


def fence(body, lang=""):
    return f"```{lang}\n{body.rstrip()}\n```"


def directive_content(kind, args, lab, t, whole):
    if kind == "include":
        f = resolve(lab, args[0])
        return f.read_text() if f.exists() else f"**MISSING include: {args[0]}**"
    if kind == "code":
        f = resolve(lab, args[0])
        return fence(f.read_text(), args[1] if len(args) > 1 else "text") if f.exists() else f"**MISSING: {args[0]}**"
    if kind == "deltas":
        part = int(dict(x.split("=") for x in args)["part"])
        blocks = [f"**{dev}**\n\n" + fence(d[part]) for dev, d in sorted(read_deltas(lab).items()) if part in d]
        return "\n\n".join(blocks) or f"*(no configuration changes in Part {part})*"
    if kind == "ticket":
        d = lab / "solutions" / "tickets" / (f"ticket-{args[0]}" if args[0].isdigit() else args[0])
        return "\n\n".join(f"**{f.stem}** (lines added to the final config)\n\n" + fence(f.read_text())
                           for f in sorted(d.glob("*.delta"))) or "**MISSING ticket deltas**"
    if kind == "table":
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_table(argparse.Namespace(topology=str(topo_file(lab)), links=False))
        return buf.getvalue()
    if kind == "objectives":
        heads = re.findall(r"^##\s+(Part\s+\d+):\s*(.+)$", whole, flags=re.M)
        return "\n".join(f"- **{p}:** {title}" for p, title in heads)
    if kind == "time":
        g = lab / "lab-guide.md"
        _, req, extra, _ = time_totals(g.read_text() if g.exists() else whole)
        depth = DEPTHS.get(lab_depth(lab) or "")
        return (f"**Estimated time:** about {fmt_minutes(req)}" + (f" (+ {fmt_minutes(extra)} optional)" if extra else "")
                + (f" · **Depth:** {depth[0]}" if depth else ""))
    return f"**UNKNOWN marker @{kind}**"


def cmd_expand(a):
    f = Path(a.file)
    lab = lab_root(f.parent)
    new = expand_text(f.read_text(), lab)
    f.write_text(new)
    missing = re.findall(r"\*\*(MISSING[^*]*|UNKNOWN[^*]*)\*\*", new)
    print(f"expand: {f.name}" + (f" - {len(missing)} problem(s): {missing[:3]}" if missing else ""))
    return 1 if missing else 0


# --------------------------------------------------------------------------- lookup (coaching mode)


def section(text, head_re, level):
    """From the first heading matching head_re to the next heading of the same or a higher level."""
    m = re.search(head_re, text, re.M)
    if not m:
        return ""
    nxt = re.search(rf"^#{{1,{level}}} ", text[m.end():], re.M)
    return text[m.start():m.end() + (nxt.start() if nxt else len(text))]


def tidy(s):
    s = re.sub(r'^<div class="answer[^"]*"></div>\n?|^<!-- @?[\w -]*(-->)?\n?', "", s, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def cmd_lookup(a):
    """Print only what coaching one step needs: that step (with its Part's intro), its hints and the answer key."""
    lab = lab_root(a.lab)
    guide = (lab / "lab-guide.md").read_text()
    kf = lab / "solutions" / "answer-key.md"
    key = kf.read_text() if kf.exists() else ""
    appendix = section(guide, r"^## Appendix A.*$", 2)
    ref = a.ref.lower().replace(" ", "")
    step = re.fullmatch(r"(\d+)(?:\.(\d+))?", ref)
    ticket = None if step else re.fullmatch(r"(?:t|ticket)(\d+)|(challenge)", ref)
    if step:
        p, s = step[1], step[2]
        part = g = section(guide, rf"^## Part {p}\b.*$", 2)
        if s and part:
            first = re.search(r"^### ", part, re.M)
            g = (part[:first.start()] if first else "") + section(part, rf"^### Step {s}\b.*$", 3)
        k = section(key, rf"^## Part {p}\b.*$", 2)
        any_step = r"\d+"
        title, pattern = f"Part {p}" + (f", Step {s}" if s else ""), rf"H{p}\.{s or any_step}[a-z]?"
    elif ticket:
        head, lvl = (rf"^### Ticket {ticket[1]}\b.*$", 3) if ticket[1] else (r"^## Part \d+: Challenge.*$", 2)
        g, k = section(guide, head, lvl), section(key, head, lvl)
        title = f"Ticket {ticket[1]}" if ticket[1] else "Challenge"
        pattern = "|".join(sorted(set(re.findall(r"\bH\d+\.\d+[a-z]?\b", g)))) or "(?!)"
    else:
        sys.exit("lookup: give a step (3.2), a whole Part (3), a ticket (t1) or 'challenge'")
    if not g:
        heads = re.findall(r"^(## Part \d+:.*|### Ticket \d+.*)$", guide, re.M)
        sys.exit(f"lookup: '{a.ref}' not found in lab-guide.md. It has:\n  " + "\n  ".join(heads))
    hint_text = "\n\n".join(tidy(m[0]) for m in
                            re.finditer(rf"^#{{2,4}}\s*(?:{pattern})\b.*?(?=^#|\Z)", appendix, re.M | re.S))
    print(f"=== Guide: {title} ===\n{tidy(g)}\n")
    print(f"=== Hints ===\n{hint_text or '(none)'}\n")
    key_title = title.split(",")[0]  # the answer key is organised per Part, not per step
    print(f"=== Answer key: {key_title} (for you, not to paste: tutoring.md §6) ===\n{tidy(k) or '(not found)'}")
    return 0


# --------------------------------------------------------------------------- build (one-shot)


def cmd_build(a):
    import contextlib, io, subprocess
    lab = lab_root(a.lab)
    topo = topo_file(lab)
    rc = 0

    def quiet(fn, ns):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = fn(ns)
        return r, buf.getvalue()

    print(quiet(cmd_configs, argparse.Namespace(lab=str(lab), force=a.force_configs))[1].strip())
    r, out = quiet(cmd_validate, argparse.Namespace(topology=str(topo)))
    print("\n".join(l for l in out.splitlines() if l.startswith("ERROR")) or "", end="")
    print(out.strip().splitlines()[-1] if out.strip() else "")
    if r:
        print("build stopped: fix the validation errors above")
        return 1
    print(quiet(cmd_assemble, argparse.Namespace(lab=str(lab)))[1].strip())
    print(quiet(cmd_tickets, argparse.Namespace(lab=str(lab)))[1].strip())
    quiet(cmd_svg, argparse.Namespace(topology=str(topo), out=str(lab / "topology" / "topology.svg")))
    _, table = quiet(cmd_table, argparse.Namespace(topology=str(topo), links=False))
    (lab / "topology" / "addressing-table.md").write_text(table)
    r1 = cmd_cml(argparse.Namespace(topology=str(topo), out=str(lab / "topology" / "cml-lab.yaml"), configs_dir=None,
                                    fallback_dir=None, title=None, nodedefs=None, format="yaml", quiet=True))
    (lab / "_work").mkdir(exist_ok=True)
    cmd_cml(argparse.Namespace(topology=str(topo), out=str(lab / "_work" / "cml-lab.json"), configs_dir=None,
                               fallback_dir=None, title=None, nodedefs=None, format="json", quiet=True))
    rc |= r1
    print("diagram, addressing table, cml-lab.yaml (+ _work/cml-lab.json for MCP import): done")
    docs = [p for p in (lab / "lab-guide.md", lab / "solutions" / "answer-key.md", lab / "README.md") if p.exists()]
    for d in docs:
        r, out = quiet(cmd_expand, argparse.Namespace(file=str(d)))
        rc |= r
        print(out.strip())
    guide = lab / "lab-guide.md"
    if guide.exists():
        r, out = quiet(cmd_lint, argparse.Namespace(guide=str(guide), lab=str(lab)))
        issues = [l for l in out.splitlines() if l.startswith("LINT")]
        print("".join("time: " + l[6:] + "\n" for l in out.splitlines() if l.startswith("TIME")), end="")
        checks = [l[6:] for l in out.splitlines() if l.startswith("CHECK")]
        if checks:
            print(f"check: {len(checks)} value(s) to verify against topology.yaml and the configs (not errors):"
                  + "".join("\n  " + c for c in checks[:20]))
        print(f"lint: {len(issues)} issue(s)" + ("".join("\n  " + l[6:] for l in issues[:15])))
        rc |= r
    if a.pdf:
        md2pdf = Path(__file__).resolve().parent / "md2pdf.py"
        title = load_topology(topo)["lab"].get("title", "Lab")
        for d, foot, prev in ((guide, title, "guide"), (lab / "solutions" / "answer-key.md", title + " - Answer Key", "answer-key")):
            if d.exists():
                r = subprocess.run([sys.executable, "-I", str(md2pdf), str(d), "--footer", foot,
                                    "--preview", str(lab / "_work" / f"preview-{prev}.png")],
                                   capture_output=True, text=True)
                print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "")
                rc |= r.returncode
    print("build: OK" if rc == 0 else "build: finished with problems (see above)")
    return rc


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate"); p.add_argument("topology"); p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("table"); p.add_argument("topology"); p.add_argument("--links", action="store_true")
    p.add_argument("--all", action="store_true", help="include interfaces without addresses")
    p.set_defaults(fn=cmd_table)
    p = sub.add_parser("svg"); p.add_argument("topology"); p.add_argument("out"); p.set_defaults(fn=cmd_svg)
    p = sub.add_parser("cml"); p.add_argument("topology"); p.add_argument("out")
    p.add_argument("--fallback-dir", help="second override folder (e.g. solutions/final-configs)")
    p.add_argument("--configs-dir", help="folder whose <device>.cfg files override the initial configs "
                   "(troubleshooting tickets, part checkpoints)")
    p.add_argument("--title", help="override the lab title (CML maximum: 64 characters)")
    p.add_argument("--nodedefs", help="JSON {node_definition: [physical interface names in slot order]}, "
                   "taken from the server's node definitions; overrides the built-in name patterns")
    p.add_argument("--format", choices=["yaml", "json"], help="default: by extension (.json -> json)")
    p.set_defaults(fn=cmd_cml)
    p = sub.add_parser("lint"); p.add_argument("guide"); p.add_argument("--lab", help="lab root folder")
    p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("configs"); p.add_argument("lab"); p.add_argument("--force", action="store_true",
                                                                        help="also overwrite hand-written configs")
    p.set_defaults(fn=cmd_configs)
    p = sub.add_parser("assemble"); p.add_argument("lab"); p.set_defaults(fn=cmd_assemble)
    p = sub.add_parser("tickets"); p.add_argument("lab"); p.set_defaults(fn=cmd_tickets)
    p = sub.add_parser("expand"); p.add_argument("file"); p.set_defaults(fn=cmd_expand)
    p = sub.add_parser("lookup", help="coaching: print one step/ticket, its hints and its answer-key section")
    p.add_argument("lab"); p.add_argument("ref", help="3.2 (step), 3 (Part), t1 (ticket) or challenge")
    p.set_defaults(fn=cmd_lookup)
    p = sub.add_parser("build"); p.add_argument("lab")
    p.add_argument("--pdf", action="store_true", help="also render guide + answer key PDFs and previews")
    p.add_argument("--force-configs", action="store_true", help="regenerate hand-written initial configs too")
    p.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
