#!/usr/bin/env python3
"""
GeminiOS Native Package Manager (`gem`)
Independent manifest-based package manager backed by GitHub repositories,
with native Arch Linux + AUR bridge and Gemini AI assistance.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tomllib
except ImportError:
    tomllib = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from arch_bridge import ArchBridge


DEFAULT_CONF_PATHS = [
    Path("/etc/gem/gem.conf"),
    SCRIPT_DIR / "gem.conf",
]


def require_root(action: str) -> bool:
    if os.geteuid() != 0:
        print(f"[gem] `{action}` requires root privileges. Run: sudo gem {action} ...", file=sys.stderr)
        return False
    return True


def load_config(conf_path: Optional[Path] = None) -> Tuple[Dict, Path]:
    target = conf_path
    if target is None:
        for p in DEFAULT_CONF_PATHS:
            if p.exists():
                target = p
                break
    if target is None or not target.exists():
        raise FileNotFoundError("gem.conf not found in /etc/gem/gem.conf or local directory")
    if tomllib is None:
        raise RuntimeError("Python 3.11+ tomllib is required to parse gem.conf")
    with target.open("rb") as fh:
        return tomllib.load(fh), target


def write_bridge_flag(conf_path: Path, bridge_name: str, enabled: bool) -> None:
    lines = conf_path.read_text(encoding="utf-8").splitlines()
    section_header = f"[bridge.{bridge_name}]"
    in_section = False
    updated = False
    out_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = (stripped == section_header)
        if in_section and stripped.startswith("enabled"):
            out_lines.append(f"enabled = {'true' if enabled else 'false'}")
            updated = True
        else:
            out_lines.append(line)
    if not updated:
        out_lines.append(f"\n{section_header}\nenabled = {'true' if enabled else 'false'}")
    conf_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


class GemPackageManager:
    def __init__(self, conf_path: Optional[Path] = None):
        self.config, self.conf_path = load_config(conf_path)
        core = self.config.get("core", {})
        self.db_dir = Path(core.get("db_dir", "/var/lib/gem"))
        self.cache_dir = Path(core.get("cache_dir", "/var/cache/gem"))
        self.root_dir = Path(core.get("root_dir", "/"))
        self.verify_sha256 = bool(core.get("verify_sha256", True))
        self.ai_enabled = bool(core.get("ai_assistant", True))
        self.geminid_url = core.get("geminid_url", "http://127.0.0.1:11435")
        self.bridge = ArchBridge(self.config)

    def _ensure_dirs(self) -> None:
        self.db_dir.mkdir(parents=True, exist_ok=True)
        (self.db_dir / "installed").mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.db_dir / "index.json"

    def _load_index(self) -> Dict:
        idx = self._index_path()
        if not idx.exists():
            return {"packages": {}}
        return json.loads(idx.read_text(encoding="utf-8"))

    def _installed_path(self, name: str) -> Path:
        return self.db_dir / "installed" / f"{name}.json"

    def is_installed(self, name: str) -> bool:
        return self._installed_path(name).exists()

    def ask_geminid(self, prompt: str) -> Optional[str]:
        if not self.ai_enabled:
            return None
        try:
            payload = json.dumps({"prompt": prompt, "prefer": "auto"}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.geminid_url}/v1/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response") if data.get("ok") else None
        except Exception:
            return None

    def sync(self) -> int:
        if not require_root("update"):
            return 1
        self._ensure_dirs()
        existing = self._load_index().get("packages", {})
        merged_packages: Dict[str, Dict] = dict(existing)
        repos = self.config.get("repo", {})
        synced_any = False
        for repo_name, repo_cfg in repos.items():
            if not repo_cfg.get("enabled", True):
                continue
            index_url = repo_cfg.get("index_url")
            if not index_url:
                owner = repo_cfg.get("owner")
                repo = repo_cfg.get("repo")
                branch = repo_cfg.get("branch", "main")
                index_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/index.json"
            print(f"[gem] Syncing GitHub manifest repo `{repo_name}` from {index_url} ...")
            try:
                with urllib.request.urlopen(index_url, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                for pkg_name, meta in data.get("packages", {}).items():
                    meta["repo"] = repo_name
                    meta["base_url"] = repo_cfg.get("base_url", index_url.rsplit("/", 1)[0])
                    merged_packages[pkg_name] = meta
                synced_any = True
                print(f"[gem] Synced {len(data.get('packages', {}))} packages from `{repo_name}`.")
            except Exception as exc:
                print(f"[gem] Note: remote `{repo_name}` unavailable ({exc}); keeping local cached index ({len(merged_packages)} packages).")

        self._index_path().write_text(json.dumps({"packages": merged_packages}, indent=2), encoding="utf-8")
        if self.bridge.is_arch_enabled() and shutil.which("pacman"):
            print("[gem] Syncing Arch Linux bridge databases...")
            subprocess.run(["pacman", "--config", str(self.bridge.pacman_conf), "-Sy", "--noconfirm"], check=False)
        if not synced_any:
            print("[gem] Tip: point [repo.geminios-main] in /etc/gem/gem.conf to your pushed GitHub `geminios-repo`.")
        return 0

    def upgrade(self, noconfirm: bool = False) -> int:
        if not require_root("upgrade"):
            return 1
        self.sync()
        if self.bridge.is_arch_enabled():
            print("[gem] Upgrading Arch Linux bridge packages...")
            rc = self.bridge.upgrade_arch(noconfirm=noconfirm)
            if rc != 0:
                return rc
        print("[gem] System upgrade complete.")
        return 0

    def _fetch_manifest(self, pkg_meta: Dict) -> Dict:
        manifest_rel = pkg_meta.get("manifest")
        base_url = pkg_meta.get("base_url", "")
        url = manifest_rel if str(manifest_rel).startswith("http") else f"{base_url}/{manifest_rel}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read()
        return tomllib.loads(raw.decode("utf-8"))

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _install_native_package(self, name: str, visited: Optional[set] = None) -> int:
        if visited is None:
            visited = set()
        if name in visited or self.is_installed(name):
            return 0
        visited.add(name)

        index = self._load_index()
        pkg_meta = index.get("packages", {}).get(name)
        if not pkg_meta:
            return 2

        try:
            manifest = self._fetch_manifest(pkg_meta)
        except Exception as exc:
            print(f"[gem] Could not fetch remote manifest for `{name}`: {exc}", file=sys.stderr)
            return 2

        pkg_section = manifest.get("package", {})
        deps = pkg_section.get("depends", [])
        for dep in deps:
            if not self.is_installed(dep):
                rc = self._install_native_package(dep, visited)
                if rc != 0 and self.bridge.is_arch_enabled():
                    self.bridge.install_arch([dep], noconfirm=True)

        source = manifest.get("source", {})
        tarball_url = source.get("url")
        expected_sha = source.get("sha256", "")
        installed_files: List[str] = []

        if tarball_url:
            archive_path = self.cache_dir / f"{name}-{pkg_section.get('version', '0')}.tar.gz"
            urllib.request.urlretrieve(tarball_url, archive_path)
            if self.verify_sha256 and expected_sha and expected_sha != "SKIP":
                actual_sha = self._sha256_file(archive_path)
                if actual_sha != expected_sha:
                    print(f"[gem] SHA256 mismatch for {name}", file=sys.stderr)
                    return 1
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isfile():
                        installed_files.append("/" + member.name.lstrip("./"))
                tf.extractall(path=self.root_dir)

        post_install = manifest.get("hooks", {}).get("post_install")
        if post_install:
            subprocess.run(["/bin/bash", "-c", post_install], check=False)

        record = {
            "name": name,
            "version": pkg_section.get("version", pkg_meta.get("version", "0.0.0")),
            "description": pkg_section.get("description", ""),
            "depends": deps,
            "files": installed_files,
            "repo": pkg_meta.get("repo", "geminios-main"),
        }
        self._installed_path(name).write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"[gem] Installed `{name}` {record['version']}.")
        return 0

    def install(self, targets: List[str], noconfirm: bool = False) -> int:
        if not require_root("install"):
            return 1
        self._ensure_dirs()
        for raw_target in targets:
            if raw_target.startswith("arch:"):
                rc = self.bridge.install_arch([raw_target.split(":", 1)[1]], noconfirm=noconfirm)
                if rc != 0:
                    return rc
                continue
            if raw_target.startswith("aur:"):
                rc = self.bridge.install_aur([raw_target.split(":", 1)[1]], noconfirm=noconfirm)
                if rc != 0:
                    return rc
                continue

            rc = self._install_native_package(raw_target)
            if rc == 2:
                if self.bridge.is_arch_enabled():
                    print(f"[gem] Checking Arch Linux bridge for `{raw_target}`...")
                    arch_rc = self.bridge.install_arch([raw_target], noconfirm=noconfirm)
                    if arch_rc == 0:
                        continue
                if self.bridge.is_aur_enabled():
                    print(f"[gem] Checking AUR bridge for `{raw_target}`...")
                    aur_rc = self.bridge.install_aur([raw_target], noconfirm=noconfirm)
                    if aur_rc == 0:
                        continue
                print(f"[gem] Package `{raw_target}` not found.", file=sys.stderr)
                hint = self.ask_geminid(
                    f"User tried `gem install {raw_target}` on GeminiOS and it was not found. "
                    f"Suggest exact package name or `sudo gem repo enable arch`."
                )
                if hint:
                    print(f"\n[Gemini Hint]\n{hint}\n")
                return 1
            elif rc != 0:
                return rc
        return 0

    def remove(self, targets: List[str]) -> int:
        if not require_root("remove"):
            return 1
        for name in targets:
            rec_path = self._installed_path(name)
            if rec_path.exists():
                record = json.loads(rec_path.read_text(encoding="utf-8"))
                for fpath in sorted(record.get("files", []), reverse=True):
                    p = Path(fpath)
                    if p.exists() and p.is_file():
                        p.unlink()
                rec_path.unlink()
                print(f"[gem] Removed native package `{name}`.")
            elif self.bridge.is_arch_enabled() and shutil.which("pacman"):
                subprocess.run(["pacman", "--config", str(self.bridge.pacman_conf), "-Rns", name], check=False)
            else:
                print(f"[gem] Package `{name}` is not installed.", file=sys.stderr)
        return 0

    def search(self, query: str, use_ai: bool = False) -> int:
        index = self._load_index()
        matches = []
        q = query.lower()
        for name, meta in index.get("packages", {}).items():
            if q in name.lower() or q in meta.get("description", "").lower():
                matches.append({
                    "name": name,
                    "version": meta.get("version", ""),
                    "description": meta.get("description", ""),
                    "source": meta.get("repo", "geminios-main"),
                })

        matches.extend(self.bridge.search_arch(query))
        matches.extend(self.bridge.search_aur(query))

        if not matches:
            print(f"[gem] No packages matched `{query}`.")
        else:
            for item in matches:
                print(f"[{item['source']}] {item['name']} ({item['version']})\n    {item['description']}")

        if use_ai:
            ai_reply = self.ask_geminid(
                f"Recommend the best Linux packages for `{query}` on GeminiOS (KDE Plasma 6, `gem` + Arch/AUR bridge)."
            )
            if ai_reply:
                print(f"\n[Gemini AI Package Recommendations]\n{ai_reply}\n")
        return 0

    def info(self, name: str) -> int:
        index = self._load_index()
        meta = index.get("packages", {}).get(name)
        if meta:
            print(json.dumps({"name": name, **meta}, indent=2))
            return 0
        if self.bridge.is_arch_enabled() and shutil.which("pacman"):
            return subprocess.run(["pacman", "--config", str(self.bridge.pacman_conf), "-Si", name]).returncode
        print(f"[gem] No info found for `{name}`.", file=sys.stderr)
        return 1

    def list_installed(self) -> int:
        inst_dir = self.db_dir / "installed"
        if not inst_dir.exists():
            print("[gem] No native packages tracked yet.")
            return 0
        for rec_file in sorted(inst_dir.glob("*.json")):
            rec = json.loads(rec_file.read_text(encoding="utf-8"))
            print(f"{rec['name']} {rec['version']}  -  {rec.get('description', '')}")
        return 0

    def repo_cmd(self, action: str, target: Optional[str]) -> int:
        if action == "list":
            print("Configured Repositories & Bridges:")
            for rname, rcfg in self.config.get("repo", {}).items():
                state = "ENABLED" if rcfg.get("enabled", True) else "DISABLED"
                print(f"  - {rname} [github-manifest] ({state}) -> {rcfg.get('base_url', '')}")
            print(f"  - arch [pacman bridge] ({'ENABLED' if self.bridge.is_arch_enabled() else 'DISABLED'})")
            print(f"  - aur  [yay/AUR bridge] ({'ENABLED' if self.bridge.is_aur_enabled() else 'DISABLED'})")
            return 0
        if not require_root(f"repo {action}"):
            return 1
        if action == "enable" and target in ("arch", "aur"):
            write_bridge_flag(self.conf_path, target, True)
            if target == "aur":
                write_bridge_flag(self.conf_path, "arch", True)
            self.config, _ = load_config(self.conf_path)
            self.bridge = ArchBridge(self.config)
            if target == "arch":
                self.bridge.enable_arch()
            else:
                self.bridge.enable_aur()
            return 0
        if action == "disable" and target in ("arch", "aur"):
            write_bridge_flag(self.conf_path, target, False)
            print(f"[gem] Disabled `{target}` bridge in {self.conf_path}.")
            return 0
        print("Usage: gem repo [list | enable <arch|aur> | disable <arch|aur>]", file=sys.stderr)
        return 1

    def doctor(self) -> int:
        print("[gem] Running package & repository health check...")
        issues = []
        if not self._index_path().exists():
            issues.append("Local manifest index missing (run `sudo gem update`).")
        if self.bridge.is_arch_enabled() and not shutil.which("pacman"):
            issues.append("Arch bridge is enabled in gem.conf, but `pacman` binary is missing.")
        if self.bridge.is_aur_enabled() and not shutil.which("fakeroot"):
            issues.append("AUR bridge needs `base-devel` (`fakeroot`, `debugedit`).")
        if self.bridge.is_aur_enabled() and not shutil.which("yay"):
            issues.append("`yay` not installed yet (using makepkg fallback; run `sudo gem repo enable aur` to bootstrap yay-bin).")
        if not issues:
            print("[gem] Everything looks healthy.")
            return 0
        for i in issues:
            print("  !", i)
        ai_fix = self.ask_geminid("Fix these GeminiOS `gem` package manager issues:\n" + "\n".join(issues))
        if ai_fix:
            print(f"\n[Gemini Doctor]\n{ai_fix}\n")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gem",
        description="GeminiOS Independent Package Manager (GitHub Manifests + Arch/AUR Bridge + Gemini AI)",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to gem.conf")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("update", help="Sync GitHub manifest repositories & Arch bridge")
    p_upg = sub.add_parser("upgrade", help="Upgrade system packages")
    p_upg.add_argument("-y", "--noconfirm", action="store_true")

    p_inst = sub.add_parser("install", help="Install package(s) (native, arch:<pkg>, aur:<pkg>)")
    p_inst.add_argument("packages", nargs="+")
    p_inst.add_argument("-y", "--noconfirm", action="store_true")

    p_rm = sub.add_parser("remove", help="Remove installed package(s)")
    p_rm.add_argument("packages", nargs="+")

    p_search = sub.add_parser("search", help="Search native, Arch, and AUR packages")
    p_search.add_argument("query")
    p_search.add_argument("--ai", action="store_true", help="Ask Gemini for recommendations too")

    p_info = sub.add_parser("info", help="Show package metadata")
    p_info.add_argument("package")

    sub.add_parser("list", help="List installed native packages")

    p_repo = sub.add_parser("repo", help="Manage repositories and Arch/AUR bridges")
    p_repo.add_argument("action", choices=["list", "enable", "disable"])
    p_repo.add_argument("target", nargs="?", choices=["arch", "aur"])

    sub.add_parser("doctor", help="Check package manager health with Gemini AI")

    args = parser.parse_args()
    pm = GemPackageManager(conf_path=args.config)

    if args.command == "update":
        return pm.sync()
    if args.command == "upgrade":
        return pm.upgrade(noconfirm=args.noconfirm)
    if args.command == "install":
        return pm.install(args.packages, noconfirm=args.noconfirm)
    if args.command == "remove":
        return pm.remove(args.packages)
    if args.command == "search":
        return pm.search(args.query, use_ai=args.ai)
    if args.command == "info":
        return pm.info(args.package)
    if args.command == "list":
        return pm.list_installed()
    if args.command == "repo":
        return pm.repo_cmd(args.action, args.target)
    if args.command == "doctor":
        return pm.doctor()
    return 0


if __name__ == "__main__":
    sys.exit(main())
