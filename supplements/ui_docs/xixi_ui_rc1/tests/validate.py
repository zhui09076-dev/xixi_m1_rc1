from pathlib import Path
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

errors = []

for rel in ["manifest.json", "STATUS.json"]:
    try:
        json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{rel}: {exc}")

for path in ROOT.glob("layouts/*.json"):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "characterSafeArea" not in data or "faceSafeArea" not in data:
            errors.append(f"{path.name}: missing safe area")
    except Exception as exc:
        errors.append(f"{path}: {exc}")

for path in ROOT.glob("components/*.json"):
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: {exc}")

for path in ROOT.glob("assets/icons/*.svg"):
    try:
        ET.parse(path)
    except Exception as exc:
        errors.append(f"{path}: {exc}")

html = (ROOT / "index.html").read_text(encoding="utf-8")
for required in [
    'id="app"', 'id="rail"', 'id="app-library"', 'id="main-panel"',
    'id="composer"', 'id="permission"', 'scripts/app.js'
]:
    if required not in html:
        errors.append(f"index.html missing {required}")

for match in re.findall(r'(?:src|href)="([^"]+)"', html):
    if match.startswith(("http:", "https:", "#")):
        continue
    if not (ROOT / match).exists():
        errors.append(f"missing linked file: {match}")

node = subprocess.run(
    ["node", "--check", str(ROOT / "scripts/app.js")],
    text=True, capture_output=True
)
if node.returncode != 0:
    errors.append("JavaScript syntax: " + node.stderr)

if errors:
    print("\n".join(errors))
    sys.exit(1)

print("JSON: OK")
print("SVG: OK")
print("HTML links: OK")
print("JavaScript syntax: OK")
print("UI static validation: OK")
