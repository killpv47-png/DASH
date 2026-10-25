"""Parse what the user sends into an uploadable Worker bundle.

Accepted inputs:
  * a single ``.js`` / ``.mjs`` / ``.cjs`` / ``.py`` file (or pasted code)
  * a ``.zip`` with the project: modules + optional ``wrangler.toml`` / ``wrangler.json(c)``
    and ``package.json``.  The main module is chosen from (in order): wrangler ``main``,
    ``package.json`` "main"/"module", ``dist/index.js``, ``src/index.js``, ``index.js``,
    ``worker.js``, ``_worker.js``, the only .js file.

Path safety from the old ZIP flow is kept (no ``..``, no absolute paths, ``__MACOSX`` /
``node_modules`` / ``.git`` ignored).  TypeScript is NOT compiled here: ``.ts`` mains are
reported as a blocker with the exact build command.
"""

from __future__ import annotations

import io
import json
import posixpath
import zipfile
from dataclasses import dataclass, field

from .analyzer import Analysis, analyze_sources, parse_wrangler

MAX_FILES = 500
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_FILE_BYTES = 25 * 1024 * 1024
UPLOAD_EXT = (".js", ".mjs", ".cjs", ".py", ".wasm", ".map", ".txt", ".html", ".json", ".sql", ".bin")
_IGNORED_DIRS = {"__MACOSX", ".git", "node_modules", "__pycache__", ".wrangler", ".DS_Store", ".github"}
CONFIG_NAMES = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")


class BundleError(Exception):
    pass


@dataclass
class Bundle:
    modules: dict[str, bytes]
    main: str
    analysis: Analysis
    config: dict = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    source_name: str = ""

    @property
    def count(self) -> int:
        return len(self.modules)

    @property
    def total_bytes(self) -> int:
        return sum(len(v) for v in self.modules.values())


def _safe_path(name: str) -> str | None:
    name = name.replace("\\", "/")
    if name.endswith("/") or "\x00" in name or ".." in name.split("/"):
        return None
    norm = posixpath.normpath(name)
    if norm.startswith(("../", "/")) or norm == ".":
        return None
    parts = norm.split("/")
    if any(p in _IGNORED_DIRS for p in parts) or parts[-1] == ".DS_Store":
        return None
    return norm


def _strip_common_root(files: dict[str, bytes]) -> dict[str, bytes]:
    roots = {p.split("/")[0] for p in files}
    if len(roots) == 1 and all("/" in p for p in files):
        pre = next(iter(roots)) + "/"
        return {p[len(pre):]: d for p, d in files.items()}
    return files


def from_code(code: str | bytes, filename: str = "worker.js") -> Bundle:
    data = code.encode() if isinstance(code, str) else code
    if not data.strip():
        raise BundleError("empty code")
    fname = posixpath.basename(filename) or "worker.js"
    if fname.endswith(".ts"):
        raise BundleError("TypeScript must be compiled first: `npx wrangler deploy --dry-run --outdir dist` "
                          "then send dist/index.js (or the whole dist folder as ZIP).")
    if not fname.endswith((".js", ".mjs", ".cjs", ".py")):
        fname = fname.rsplit(".", 1)[0] + ".js" if "." in fname else fname + ".js"
    text = data.decode("utf-8", errors="replace")
    a = analyze_sources({fname: text}, fname)
    return Bundle(modules={fname: data}, main=fname, analysis=a, source_name=filename)


def _pick_main(files: dict[str, bytes], cfg: dict) -> str | None:
    cands: list[str] = []
    if cfg.get("main"):
        cands.append(posixpath.normpath(str(cfg["main"]).lstrip("./")))
    if "package.json" in files:
        try:
            pj = json.loads(files["package.json"])
            for k in ("module", "main"):
                if pj.get(k):
                    cands.append(posixpath.normpath(str(pj[k]).lstrip("./")))
        except Exception:
            pass
    cands += ["dist/index.js", "dist/worker.js", "dist/_worker.js", "src/index.js", "src/worker.js", "index.js",
              "worker.js", "_worker.js", "src/entry.py", "src/main.py", "main.py", "worker.py"]
    for c in cands:
        if c in files:
            return c
        # wrangler main may point to .ts while a compiled .js sits in dist/
    js = [p for p in files if p.endswith((".js", ".mjs"))]
    if len(js) == 1:
        return js[0]
    for c in cands:
        if c.endswith(".ts"):
            return c
    return None


def from_zip(data: bytes, source_name: str = "project.zip") -> Bundle:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise BundleError("not a valid ZIP file") from e
    files: dict[str, bytes] = {}
    skipped: list[str] = []
    total = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        path = _safe_path(info.filename)
        if path is None:
            skipped.append(info.filename)
            continue
        if info.file_size > MAX_FILE_BYTES or len(files) >= MAX_FILES:
            skipped.append(f"{info.filename} (too large / too many files)")
            continue
        content = zf.read(info)
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise BundleError("ZIP contents exceed 60 MB")
        files[path] = content
    if not files:
        raise BundleError("ZIP is empty")
    files = _strip_common_root(files)

    cfg: dict = {}
    cfg_name = next((c for c in CONFIG_NAMES if c in files), None)
    if cfg_name:
        try:
            cfg = parse_wrangler(cfg_name, files[cfg_name].decode("utf-8", errors="replace"))
        except Exception as e:
            skipped.append(f"{cfg_name} (unparseable: {e})")
    main = _pick_main(files, cfg)
    if not main:
        raise BundleError("Could not find the entry module. Add wrangler.toml with `main = \"…\"` or name it index.js / worker.js.")
    if main.endswith(".ts"):
        raise BundleError(f"Entry {main} is TypeScript — build first (`npx wrangler deploy --dry-run --outdir dist`) "
                          "and send the dist/ output, or include the compiled .js.")

    # Upload only runtime modules; keep paths relative to the main module's directory
    base = posixpath.dirname(main)
    modules: dict[str, bytes] = {}
    for p, d in files.items():
        if p in CONFIG_NAMES or p in ("package.json", "package-lock.json", "README.md", "tsconfig.json") or p.endswith(".ts"):
            continue
        if not p.endswith(UPLOAD_EXT):
            continue
        rel = posixpath.relpath(p, base) if base else p
        if rel.startswith(".."):
            continue  # outside the entry directory (e.g. tests/, scripts/)
        if p.endswith((".json", ".html", ".txt", ".sql")) and not _is_imported(rel, files, main):
            continue  # don't upload docs/data unless the code imports them
        modules[rel] = d
    main_rel = posixpath.relpath(main, base) if base else main
    texts = {k: v.decode("utf-8", errors="replace") for k, v in modules.items() if k.endswith((".js", ".mjs", ".cjs", ".py"))}
    a = analyze_sources(texts, main_rel, config=cfg)
    a.config_file = cfg_name
    return Bundle(modules=modules, main=main_rel, analysis=a, config=cfg, skipped=skipped, source_name=source_name)


def _is_imported(rel: str, files: dict[str, bytes], main: str) -> bool:
    needle = posixpath.basename(rel)
    for p, d in files.items():
        if p.endswith((".js", ".mjs", ".py")) and needle.encode() in d:
            return True
    return False


def from_upload(filename: str, data: bytes) -> Bundle:
    low = (filename or "").lower()
    if low.endswith(".zip") or data[:4] == b"PK\x03\x04":
        return from_zip(data, filename)
    return from_code(data, filename or "worker.js")
