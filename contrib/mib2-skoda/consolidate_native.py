#!/usr/bin/env python3
"""Fail-closed one-shot consolidation from tested P6 sources into fork main.
Inputs: patched pinned zakklmv checkout, then fork checkout.
No P8 changes, build outputs, credentials, or research fixtures are copied.
"""
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE_REV = "fd7a22fa1f503695309ec9efad0e48b2d900349f"
DIPLAY_REV = "28d6002ba00320f0ba745212160b08759e4f60b9"
DIPLAY_DATE = "2026-10-28"  # Verified DiPlay commit UTC date
CODE_ROOTS = ("src/", "webui/", "gradle/", "native/", "packaging/")
CODE_FILES = {"build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat"}
VENDOR_ROOTS = ("shared/", "docs/licenses/dependencies/")
VENDOR_FILES = {"LICENSE", "docs/THIRD_PARTY_NOTICES.md"}
MAX_FILE_BYTES = 8 * 1024 * 1024

def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.PIPE).decode().strip()

def tracked_and_added(path):
    files = set()
    for argv in (("ls-files", "-z"), ("ls-files", "--others", "--exclude-standard", "-z")):
        raw = subprocess.check_output(["git", "-C", str(path), *argv])
        files.update(v.decode("utf-8") for v in raw.split(b"\0") if v)
    return sorted(files)

def transfer(source, dest, rel):
    if rel.startswith("/") or ".." in Path(rel).parts or "\\" in rel:
        raise RuntimeError("UNSAFE_PATH " + rel)
    src = source / rel
    if not src.is_file() or src.is_symlink() or src.stat().st_size > MAX_FILE_BYTES:
        raise RuntimeError("INVALID_FILE " + str(src))
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)

if len(sys.argv) != 3:
    raise SystemExit("usage: consolidate_native.py PATCHED_CHECKOUT FORK_CHECKOUT")
source, dest = (Path(x).resolve() for x in sys.argv[1:])
if git(source, "rev-parse", "HEAD") != SOURCE_REV:
    raise RuntimeError("SOURCE_PIN_DRIFT")
if git(source / "upstream", "rev-parse", "HEAD") != DIPLAY_REV:
    raise RuntimeError("DIPLAY_PIN_DRIFT")
if git(dest, "rev-parse", "--abbrev-ref", "HEAD") != "main":
    raise RuntimeError("NOT_ON_MAIN")
if (dest / "contrib/mib2-skoda/patchchain/UPSTREAM_REVISION.txt").read_text().strip() != SOURCE_REV:
    raise RuntimeError("FORK_PIN_DRIFT")

app = [p for p in tracked_and_added(source) if p.startswith(CODE_ROOTS) or p in CODE_FILES]
vendor = [p for p in tracked_and_added(source / "upstream") if p.startswith(VENDOR_ROOTS) or p in VENDOR_FILES]
if len(app) < 150 or len(vendor) < 120:
    raise RuntimeError(f"INCOMPLETE_SOURCE app={len(app)} vendor={len(vendor)}")
for root, paths in ((source, app), (source / "upstream", vendor)):
    for p in paths:
        s = root / p
        if not s.is_file() or s.is_symlink() or s.stat().st_size > MAX_FILE_BYTES:
            raise RuntimeError("INVALID_SOURCE " + str(s))
for p in ("src", "webui", "gradle", "native", "packaging"):
    target = dest / p
    if target.is_symlink():
        raise RuntimeError("TARGET_SYMLINK " + str(target))
    if target.is_dir():
        shutil.rmtree(target)
for p in app:
    transfer(source, dest, p)

# DiPlay shared core used by gradle/upstream.gradle.kts is published in this
# fork as tracked source, with pinned provenance, instead of as a dirty gitlink.
subprocess.run(["git", "-C", str(dest), "rm", "--cached", "-f", "upstream"], check=True)
up = dest / "upstream"
if up.is_symlink():
    raise RuntimeError("UPSTREAM_IS_SYMLINK")
if up.is_dir():
    shutil.rmtree(up)
for p in vendor:
    transfer(source / "upstream", up, p)
gitmodules = dest / ".gitmodules"
if gitmodules.exists():
    original = gitmodules.read_text()
    if original.count("[submodule ") != 1 or "path = upstream" not in original:
        raise RuntimeError("UNKNOWN_GITMODULE")
    gitmodules.unlink()
(up / "VENDOR_PROVENANCE.md").write_text(
    "# Vendored DiPlay portable core\n\n"
    "Original project: https://github.com/shihabal3amri/DiPlay\n\n"
    f"Pinned DiPlay revision: {DIPLAY_REV}.\n"
    f"ChairPlay source base: zakklmv/ChairPlay {SOURCE_REV}.\n\n"
    "This folder carries the DiPlay shared module plus required licence and "
    "third-party notices. P6 AirPlay/cluster changes are directly tracked "
    "here rather than hidden as dirty submodule edits. Original GPL and "
    "third-party notices remain in place. P8 is NOT included.\n",
    encoding="utf-8",
)
upgradle = dest / "gradle/upstream.gradle.kts"
text = upgradle.read_text(encoding="utf-8")
text = text.replace(
    "// The portable CarPlay core is compiled from the Android library's own sources in the DiPlay submodule\n"
    "// (upstream/), so DiPlay's changes come in by moving the submodule.",
    "// The portable CarPlay core is compiled from the tracked DiPlay shared sources in upstream/.\n"
    "// P6 protocol modifications are native fork sources, not uncommitted submodule edits.",
)
upgradle.write_text(text, encoding="utf-8", newline="\n")
build = dest / "build.gradle.kts"
text = build.read_text(encoding="utf-8")
text = text.replace('"app" to commit(root), "core" to commit(root.resolve("upstream"))',
                    f'"app" to commit(root), "core" to listOf("{DIPLAY_REV[:8]}", "{DIPLAY_DATE}")')
if '"core" to commit(root.resolve("upstream"))' in text:
    raise RuntimeError("MISLEADING_SUBMODULE_VERSION")
build.write_text(text, encoding="utf-8", newline="\n")
area = (dest / "src/main/kotlin/io/github/numberonebot/chairplay/AltscreenView.kt").read_text()
info = (dest / "upstream/shared/src/main/java/com/shilapi/xcertplay/airplay/AirPlayInfoPlist.kt").read_text()
if "clusterGeometryMatchesNegotiated" not in area or 'put("adjacentViewAreas"' not in info:
    raise RuntimeError("P6_NATIVE_GUARDS_MISSING")
if gitmodules.exists():
    raise RuntimeError("SUBMODULE_LEFTOVER")
print(f"NATIVE_SOURCE_STAGED app_files={len(app)} diplay_files={len(vendor)}")
