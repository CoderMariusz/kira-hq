#!/usr/bin/env python3
"""Generate data.json for KiraLtd HQ dashboard from live Paperclip API."""
import json, urllib.request, re, sys
from datetime import datetime, timezone
from collections import defaultdict

BASE = "http://localhost:3100"
AUTH = "pcp_d64b9b257a79082b82109841fe7d366d4d7ff569cc0f5d7c"
COMPANY = "91191a79-e592-472a-98b4-c73a05b98225"
SKIP_PROJECTS = {"Add Agencts"}

def api(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {AUTH}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
            for key in ("projects","agents","issues","data"):
                if key in d: return d[key]
            return d if isinstance(d, list) else []
    except Exception as e:
        print(f"API error {path}: {e}", file=sys.stderr)
        return []

def main():
    projects_raw = api(f"/api/companies/{COMPANY}/projects")
    agents_raw   = api(f"/api/companies/{COMPANY}/agents")

    projects_data = []
    for p in projects_raw:
        if p["name"] in SKIP_PROJECTS: continue
        issues = api(f"/api/companies/{COMPANY}/issues?projectId={p['id']}&limit=200")
        active = [i for i in issues if i.get("status") not in ("cancelled",)]
        by_status = defaultdict(list)
        for i in active: by_status[i["status"]].append(i)

        epics = defaultdict(lambda: {"done":0,"total":0})
        for i in active:
            t = i.get("title","")
            m = re.search(r'FP-?(\d+)|EP-?(\d+)|E(\d+)|KIR-(\d+)', t)
            if m:
                ep = int(next(g for g in m.groups() if g is not None))
                epics[ep]["total"] += 1
                if i.get("status") == "done": epics[ep]["done"] += 1

        projects_data.append({
            "id":         p["id"],
            "name":       p["name"],
            "status":     p.get("status",""),
            "total":      len(active),
            "done":       len(by_status["done"]),
            "in_progress":len(by_status["in_progress"]),
            "todo":       len(by_status["todo"]),
            "backlog":    len(by_status["backlog"]),
            "in_review":  len(by_status["in_review"]),
            "epics":      {str(k):v for k,v in sorted(epics.items())},
            "issues":     active,
        })

    agents_data = [{
        "id":            a["id"],
        "name":          a["name"],
        "status":        a.get("status","idle"),
        "adapter":       a.get("adapterType","?"),
        "lastHeartbeat": a.get("lastHeartbeatAt",""),
    } for a in agents_raw]

    out = {
        "projects":  projects_data,
        "agents":    agents_data,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    with open("data.json","w") as f:
        json.dump(out, f, separators=(",",":"))
    print(f"Generated data.json — {len(projects_data)} projects, {len(agents_data)} agents")

if __name__ == "__main__":
    main()
