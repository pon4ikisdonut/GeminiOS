#!/usr/bin/env python3
"""
GeminiOS Native Package Manager (`gem`)
Independent manifest-based package manager backed by GitHub repositories,
with native Arch Linux + AUR bridge, custom repository support, system component
updates, and Gemini AI assistance.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
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

SYSTEM_COMPONENTS = [
    "geminios-core",
    "geminid",
    "gemini-cli",
    "gemini-overlay",
    "gemini-oobe",
    "geminios-plasma-m3",
    "geminios-plymouth",
    "geminios-sddm",
    "ollama-gemma",
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


def add_repo_config(conf_path: Path, name: str, source: str, branch: str = "main", repo_type: str = "auto") -> Dict:
    content = conf_path.read_text(encoding="utf-8")
    
    # Check if GitHub repo format "owner/repo"
    if "/" in source and not source.startswith("http://") and not source.startswith("https://") and not source.startswith("file://"):
        parts = source.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}"
        index_url = f"{base_url}/index.json"
        repo_type = "github-manifest"
        repo_data = {
            "enabled": True,
            "type": repo_type,
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "base_url": base_url,
            "index_url": index_url,
        }
    else:
        index_url = source
        base_url = source.rsplit("/", 1)[0]
        repo_type = "direct" if repo_type == "auto" else repo_type
        repo_data = {
            "enabled": True,
            "type": repo_type,
            "index_url": index_url,
            "base_url": base_url,
        }

    section_header = f"[repo.{name}]"
    lines = content.splitlines()
    new_lines = []
    in_target = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == section_header:
                in_target = True
                continue
            elif in_target:
                in_target = False
        if not in_target:
            new_lines.append(line)
            
    new_section = [f"\n{section_header}"]
    for k, v in repo_data.items():
        if isinstance(v, bool):
            new_section.append(f"{k} = {'true' if v else 'false'}")
        else:
            new_section.append(f'{k} = "{v}"')
            
    conf_path.write_text("\n".join(new_lines).strip() + "\n" + "\n".join(new_section) + "\n", encoding="utf-8")
    return repo_data


def remove_repo_config(conf_path: Path, name: str) -> bool:
    content = conf_path.read_text(encoding="utf-8")
    section_header = f"[repo.{name}]"
    lines = content.splitlines()
    new_lines = []
    in_target = False
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == section_header:
                in_target = True
                found = True
                continue
            elif in_target:
                in_target = False
        if not in_target:
            new_lines.append(line)
    if found:
        conf_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
    return found


def set_repo_enabled(conf_path: Path, target: str, enabled: bool) -> bool:
    content = conf_path.read_text(encoding="utf-8")
    if target in ("arch", "aur"):
        section_header = f"[bridge.{target}]"
    else:
        section_header = f"[repo.{target}]"
        
    lines = content.splitlines()
    new_lines = []
    in_target = False
    found = False
    updated_flag = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped == section_header:
                in_target = True
                found = True
            elif in_target:
                in_target = False
        if in_target and stripped.startswith("enabled"):
            new_lines.append(f"enabled = {'true' if enabled else 'false'}")
            updated_flag = True
        else:
            new_lines.append(line)
            
    if found and not updated_flag:
        idx = -1
        for i, l in enumerate(new_lines):
            if l.strip() == section_header:
                idx = i
                break
        if idx != -1:
            new_lines.insert(idx + 1, f"enabled = {'true' if enabled else 'false'}")
            
    if found:
        conf_path.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
    return found


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
        p = self.db_dir / "index.json"
        if not p.exists():
            local_fallback = SCRIPT_DIR.parent.parent / "geminios-repo/index.json"
            if local_fallback.exists():
                return local_fallback
        return p

    def _load_index(self) -> Dict:
        idx = self._index_path()
        if not idx.exists():
            return {"packages": {}}
        try:
            return json.loads(idx.read_text(encoding="utf-8"))
        except Exception:
            return {"packages": {}}

    def _installed_path(self, name: str) -> Path:
        return self.db_dir / "installed" / f"{name}.json"

    def is_installed(self, name: str) -> bool:
        return self._installed_path(name).exists()

    def get_installed_package(self, name: str) -> Optional[Dict]:
        p = self._installed_path(name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

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
            if repo_name in ("arch", "aur"):
                continue
            if not repo_cfg.get("enabled", True):
                continue
            index_url = repo_cfg.get("index_url")
            if not index_url:
                owner = repo_cfg.get("owner")
                rname = repo_cfg.get("repo")
                branch = repo_cfg.get("branch", "main")
                if owner and rname:
                    index_url = f"https://raw.githubusercontent.com/{owner}/{rname}/{branch}/index.json"
            if not index_url or not any(str(index_url).startswith(p) for p in ("http://", "https://", "file://")):
                continue

            print(f"[gem] Fetching manifest index from [{repo_name}] ({index_url})...")
            try:
                req = urllib.request.Request(index_url, headers={"User-Agent": "GeminiOS-Gem/1.0.1"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    pkgs = data.get("packages", {})
                    base_url = repo_cfg.get("base_url") or index_url.rsplit("/", 1)[0]
                    for pname, pmeta in pkgs.items():
                        pmeta["repo"] = repo_name
                        pmeta["base_url"] = base_url
                        merged_packages[pname] = pmeta
                    synced_any = True
                    print(f"[gem] Synchronized [{repo_name}]: {len(pkgs)} packages available.")
            except Exception as exc:
                print(f"[gem] Warning: Could not sync repo `{repo_name}`: {exc}", file=sys.stderr)

        if synced_any or not self._index_path().exists():
            payload = {
                "repository": "geminios-merged",
                "version": "1.0.1",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "packages": merged_packages,
            }
            self._index_path().write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[gem] Total available packages in repository index: {len(merged_packages)}")

        if self.bridge.is_arch_enabled():
            print("[gem] Synchronizing ecosystem binary repository mirrors...")
            self.bridge.sync_arch()

        return 0

    def _fetch_manifest(self, pkg_meta: Dict) -> Dict:
        if "url" in pkg_meta and "version" in pkg_meta:
            return {
                "package": {
                    "name": pkg_meta.get("name", ""),
                    "version": pkg_meta.get("version", "0.0.0"),
                    "license": pkg_meta.get("license", "GPL"),
                    "arch": pkg_meta.get("arch", "x86_64"),
                    "description": pkg_meta.get("description", ""),
                    "depends": pkg_meta.get("depends", []),
                },
                "source": {
                    "url": pkg_meta.get("url"),
                    "sha256": pkg_meta.get("sha256", "SKIP"),
                },
                "hooks": pkg_meta.get("hooks", {}),
            }

        manifest_rel = pkg_meta.get("manifest")
        base_url = pkg_meta.get("base_url", "")
        url = manifest_rel if str(manifest_rel).startswith("http") else f"{base_url}/{manifest_rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "GeminiOS-Gem/1.0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
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
        if name in visited:
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
            url_filename = tarball_url.split("/")[-1].split("?")[0]
            archive_path = self.cache_dir / url_filename
            print(f"[gem] Downloading `{name}` ({url_filename})...")
            req = urllib.request.Request(tarball_url, headers={"User-Agent": "GeminiOS-Gem/1.0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(archive_path, "wb") as out_f:
                shutil.copyfileobj(resp, out_f)

            if self.verify_sha256 and expected_sha and expected_sha != "SKIP":
                actual_sha = self._sha256_file(archive_path)
                if actual_sha != expected_sha:
                    print(f"[gem] SHA256 mismatch for {name}: expected {expected_sha}, got {actual_sha}", file=sys.stderr)
                    return 1

            print(f"[gem] Unpacking `{name}`...")
            if str(archive_path).endswith(".zst") or shutil.which("tar"):
                cmd = ["tar", "--warning=no-unknown-keyword", "-xf", str(archive_path), "-C", str(self.root_dir)]
                for excl in [".PKGINFO", ".BUILDINFO", ".MTREE", ".INSTALL"]:
                    cmd.extend(["--exclude", excl])
                subprocess.run(cmd, check=True)

                proc = subprocess.run(["tar", "-tf", str(archive_path)], capture_output=True, text=True, check=True)
                for line in proc.stdout.splitlines():
                    clean = line.strip().lstrip("./")
                    if clean and not clean.endswith("/") and not clean.startswith("."):
                        installed_files.append("/" + clean)
            else:
                with tarfile.open(archive_path, "r:*") as tf:
                    for member in tf.getmembers():
                        if member.isfile() and not member.name.startswith("."):
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
            "is_system": name in SYSTEM_COMPONENTS,
        }
        self._installed_path(name).write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"[gem] Installed `{name}` {record['version']}.")
        return 0

    def install(self, targets: List[str], noconfirm: bool = False) -> int:
        if not require_root("install"):
            return 1
        self._ensure_dirs()
        for target in targets:
            if target.startswith("arch:"):
                pkg = target.split(":", 1)[1]
                if not self.bridge.is_arch_enabled():
                    print("[gem] Enabling upstream ecosystem bridge...")
                    self.repo_cmd("enable", "arch")
                self.bridge.install_arch([pkg], noconfirm=noconfirm)
                continue

            if target.startswith("aur:"):
                pkg = target.split(":", 1)[1]
                if not self.bridge.is_aur_enabled():
                    print("[gem] Enabling community AUR repository bridge...")
                    self.repo_cmd("enable", "aur")
                self.bridge.install_aur([pkg], noconfirm=noconfirm)
                continue

            rc = self._install_native_package(target)
            if rc == 0:
                continue
            if rc == 2:
                print(f"[gem] `{target}` not found in native GEM manifests.")
                if self.bridge.is_arch_enabled():
                    print(f"[gem] Resolving `{target}` from upstream binary mirrors...")
                    rc_arch = self.bridge.install_arch([target], noconfirm=noconfirm)
                    if rc_arch == 0:
                        continue
                if self.bridge.is_aur_enabled():
                    print(f"[gem] Resolving `{target}` from community repository...")
                    rc_aur = self.bridge.install_aur([target], noconfirm=noconfirm)
                    if rc_aur == 0:
                        continue
                print(f"[gem] Error: Package `{target}` could not be found.", file=sys.stderr)
                return 1
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
                matches.append((name, meta.get("version", "?"), meta.get("description", ""), meta.get("repo", "geminios-main")))

        print(f"[gem] Found {len(matches)} package(s) matching '{query}':")
        for name, ver, desc, rname in matches[:40]:
            inst = "[installed]" if self.is_installed(name) else ""
            print(f"  * {name} ({ver}) [{rname}] {inst}\n      {desc}")
        if len(matches) > 40:
            print(f"  ... and {len(matches) - 40} more matching packages.")

        if self.bridge.is_arch_enabled():
            print(f"\n[gem] Searching upstream binary mirrors for '{query}'...")
            self.bridge.search_arch(query)

        if self.bridge.is_aur_enabled():
            print(f"\n[gem] Searching AUR for '{query}'...")
            self.bridge.search_aur(query)

        if use_ai:
            ai_ans = self.ask_geminid(f"Recommend best Linux CLI and GUI packages for: {query}")
            if ai_ans:
                print(f"\n[Gemini AI Recommendations]\n{ai_ans}")

        return 0

    def info(self, name: str) -> int:
        index = self._load_index()
        meta = index.get("packages", {}).get(name)
        if not meta:
            print(f"[gem] Package `{name}` not found in manifest index.", file=sys.stderr)
            return 1
        print(f"Package:     {name}")
        print(f"Version:     {meta.get('version', 'unknown')}")
        print(f"Repository:  {meta.get('repo', 'geminios-main')}")
        print(f"License:     {meta.get('license', 'unknown')}")
        print(f"Arch:        {meta.get('arch', 'x86_64')}")
        print(f"Description: {meta.get('description', '')}")
        print(f"Depends:     {', '.join(meta.get('depends', []))}")
        print(f"Installed:   {'Yes' if self.is_installed(name) else 'No'}")
        if "url" in meta:
            print(f"Source URL:  {meta.get('url')}")
        return 0

    def list_installed(self, system_only: bool = False) -> int:
        self._ensure_dirs()
        inst_dir = self.db_dir / "installed"
        records = []
        for p in inst_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if system_only and not data.get("is_system") and data.get("name") not in SYSTEM_COMPONENTS:
                    continue
                records.append(data)
            except Exception:
                pass
        records.sort(key=lambda r: r.get("name", ""))
        title = "GeminiOS System Components" if system_only else "Installed Native GEM Packages"
        print(f"[gem] {title} ({len(records)}):")
        for r in records:
            sys_tag = " [system]" if r.get("is_system") or r.get("name") in SYSTEM_COMPONENTS else ""
            print(f"  * {r.get('name')} ({r.get('version', '?')}){sys_tag}")
            if r.get("description"):
                print(f"      {r.get('description')}")
        return 0

    def system_check(self) -> int:
        index = self._load_index().get("packages", {})
        print("[gem] GeminiOS System Components Status:")
        print(f"{'Component':<24} {'Installed':<12} {'Available':<12} {'Status'}")
        print("-" * 65)

        for comp in SYSTEM_COMPONENTS:
            inst = self.get_installed_package(comp)
            inst_ver = inst.get("version") if inst else "1.0.1"
            avail = index.get(comp, {})
            avail_ver = avail.get("version", inst_ver)

            if inst_ver != avail_ver:
                status = "UPDATE AVAILABLE"
            else:
                status = "Up to date"
            print(f"{comp:<24} {inst_ver:<12} {avail_ver:<12} {status}")
        return 0

    def system_update(self, components: Optional[List[str]] = None, force: bool = False) -> int:
        if not require_root("system update"):
            return 1
        self.sync()
        index = self._load_index().get("packages", {})
        targets = components if components else SYSTEM_COMPONENTS

        updated = 0
        for comp in targets:
            inst = self.get_installed_package(comp)
            inst_ver = inst.get("version") if inst else "1.0.1"
            avail = index.get(comp, {})
            avail_ver = avail.get("version", inst_ver)

            if force or inst_ver != avail_ver or not self.is_installed(comp):
                print(f"[gem] Updating system component `{comp}` ({inst_ver} -> {avail_ver})...")
                rc = self._install_native_package(comp)
                if rc == 0:
                    updated += 1
                    # Restart services if relevant
                    if comp == "geminid":
                        subprocess.run(["systemctl", "daemon-reload"], check=False)
                        subprocess.run(["systemctl", "restart", "geminid", "geminios-panic-guard"], check=False)
                    elif comp == "geminios-plasma-m3":
                        subprocess.run(["kbuildsycoca6"], check=False)

        print(f"[gem] System components update complete. {updated} component(s) updated.")
        return 0

    def upgrade(self, noconfirm: bool = False, system_only: bool = False) -> int:
        if not require_root("upgrade"):
            return 1
        self.sync()

        # 1. Update system components
        print("[gem] Checking GeminiOS system components...")
        self.system_update(force=False)

        if system_only:
            return 0

        # 2. Update native user packages
        self._ensure_dirs()
        index = self._load_index().get("packages", {})
        inst_dir = self.db_dir / "installed"
        for p in inst_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                name = data.get("name")
                if not name or name in SYSTEM_COMPONENTS:
                    continue
                cur_ver = data.get("version")
                avail = index.get(name)
                if avail and avail.get("version") != cur_ver:
                    print(f"[gem] Upgrading package `{name}` ({cur_ver} -> {avail.get('version')})...")
                    self._install_native_package(name)
            except Exception:
                pass

        # 3. Update upstream binary ecosystem packages
        if self.bridge.is_arch_enabled():
            print("[gem] Upgrading ecosystem binary packages...")
            rc = self.bridge.upgrade_arch(noconfirm=noconfirm)
            if rc != 0:
                return rc

        print("[gem] Full system & package upgrade complete.")
        return 0

    def repo_cmd(self, action: str, target: Optional[str] = None, source: Optional[str] = None, branch: str = "main") -> int:
        if action == "list":
            self.config, _ = load_config(self.conf_path)
            repos = self.config.get("repo", {})
            index = self._load_index().get("packages", {})
            print("[gem] Configured Package Repositories:")
            for rname, rcfg in repos.items():
                if rname in ("arch", "aur"):
                    continue
                state = "ENABLED" if rcfg.get("enabled", True) else "DISABLED"
                rtype = rcfg.get("type", "github-manifest")
                url = rcfg.get("index_url") or rcfg.get("base_url", "")
                pkg_count = sum(1 for m in index.values() if m.get("repo", "geminios-main") == rname)
                print(f"  * {rname} [{rtype}] ({state})\n      URL: {url}\n      Packages: {pkg_count} available")
            print("\n  Package Ecosystem Bridges:")
            print(f"  * arch [pacman official repos] ({'ENABLED' if self.bridge.is_arch_enabled() else 'DISABLED'})")
            print(f"  * aur  [Arch User Repository]  ({'ENABLED' if self.bridge.is_aur_enabled() else 'DISABLED'})")
            return 0

        if action == "init":
            if not target:
                print("Usage: gem repo init <directory_path> [--name <repo_name>]", file=sys.stderr)
                return 1
            return self._repo_init(Path(target), name=source)

        if not require_root(f"repo {action}"):
            return 1

        if action == "add":
            if not target or not source:
                print("Usage: gem repo add <repo_name> <github_user/repo | url> [--branch <branch>]", file=sys.stderr)
                return 1
            if target.lower() in ("arch", "aur"):
                print(f"[gem] `{target}` is a built-in ecosystem bridge. Use `sudo gem repo enable {target}` instead.", file=sys.stderr)
                return 1
            if not ("/" in source or any(source.startswith(p) for p in ("http://", "https://", "file://"))):
                print(f"[gem] Error: Invalid source `{source}`. Expected GitHub `owner/repo` or valid URL to index.json.", file=sys.stderr)
                return 1
            repo_data = add_repo_config(self.conf_path, target, source, branch=branch)
            print(f"[gem] Added repository `{target}` -> {repo_data.get('index_url')}")
            print(f"[gem] Syncing repository `{target}`...")
            self.config, _ = load_config(self.conf_path)
            self.sync()
            return 0

        if action == "remove":
            if not target:
                print("Usage: gem repo remove <repo_name>", file=sys.stderr)
                return 1
            if target in ("arch", "aur"):
                print("[gem] Bridges `arch` and `aur` cannot be removed, use `disable`.", file=sys.stderr)
                return 1
            if remove_repo_config(self.conf_path, target):
                print(f"[gem] Successfully removed repository `{target}` from {self.conf_path}.")
                self.config, _ = load_config(self.conf_path)
                return 0
            else:
                print(f"[gem] Repository `{target}` not found in {self.conf_path}.", file=sys.stderr)
                return 1

        if action == "enable":
            if not target:
                print("Usage: gem repo enable <arch | aur | repo_name>", file=sys.stderr)
                return 1
            if target in ("arch", "aur"):
                set_repo_enabled(self.conf_path, target, True)
                if target == "aur":
                    set_repo_enabled(self.conf_path, "arch", True)
                self.config, _ = load_config(self.conf_path)
                self.bridge = ArchBridge(self.config)
                if target == "arch":
                    self.bridge.enable_arch()
                else:
                    self.bridge.enable_aur()
                return 0
            else:
                if set_repo_enabled(self.conf_path, target, True):
                    print(f"[gem] Enabled repository `{target}`.")
                    self.config, _ = load_config(self.conf_path)
                    self.sync()
                    return 0
                else:
                    print(f"[gem] Repository `{target}` not found.", file=sys.stderr)
                    return 1

        if action == "disable":
            if not target:
                print("Usage: gem repo disable <arch | aur | repo_name>", file=sys.stderr)
                return 1
            if set_repo_enabled(self.conf_path, target, False):
                print(f"[gem] Disabled `{target}` in {self.conf_path}.")
                self.config, _ = load_config(self.conf_path)
                return 0
            else:
                print(f"[gem] Repository or bridge `{target}` not found.", file=sys.stderr)
                return 1

        print("Usage: gem repo [list | add <name> <source> | remove <name> | enable <name> | disable <name> | init <dir>]", file=sys.stderr)
        return 1

    def _repo_init(self, target_dir: Path, name: Optional[str] = None) -> int:
        target_dir = target_dir.resolve()
        repo_name = name or target_dir.name
        packages_dir = target_dir / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)
        
        index_file = target_dir / "index.json"
        if not index_file.exists():
            index_data = {
                "repository": repo_name,
                "version": "1.0.0",
                "architecture": "x86_64",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "packages": {
                    "example-tool": {
                        "version": "1.0.0",
                        "description": "Example custom package for GeminiOS",
                        "manifest": "packages/example-tool.gem.toml"
                    }
                }
            }
            index_file.write_text(json.dumps(index_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            
        example_manifest = packages_dir / "example-tool.gem.toml"
        if not example_manifest.exists():
            example_manifest.write_text("""[package]
name = "example-tool"
version = "1.0.0"
license = "MIT"
arch = "x86_64"
description = "Example custom tool for GeminiOS"
depends = []

[source]
url = "https://example.com/example-tool-1.0.0.tar.gz"
sha256 = "SKIP"

[hooks]
post_install = "echo 'example-tool installed successfully!' || true"
""", encoding="utf-8")
            
        readme_file = target_dir / "README.md"
        if not readme_file.exists():
            readme_file.write_text(f"""# {repo_name} — GeminiOS Custom Package Repository

Custom package repository for GeminiOS package manager (`gem`).

## How to add this repository to GeminiOS:
```bash
sudo gem repo add {repo_name} <github-username>/{repo_name}
sudo gem update
sudo gem install example-tool
```
""", encoding="utf-8")
            
        print(f"[gem] Initialized new custom repository in {target_dir}")
        print(f"[gem] Next steps:")
        print(f"  1. Add your package manifests in {packages_dir}/<pkg>.gem.toml")
        print(f"  2. Push to GitHub: https://github.com/<user>/{repo_name}")
        print(f"  3. Add to your system: sudo gem repo add {repo_name} <user>/{repo_name}")
        return 0

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
    
    p_upg = sub.add_parser("upgrade", help="Upgrade system packages & GeminiOS components")
    p_upg.add_argument("-y", "--noconfirm", action="store_true")
    p_upg.add_argument("--system", action="store_true", help="Upgrade only GeminiOS system components")

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

    p_list = sub.add_parser("list", help="List installed packages")
    p_list.add_argument("--system", action="store_true", help="List only core GeminiOS system components")

    # System components management
    p_sys = sub.add_parser("system", help="Manage and update GeminiOS system components")
    p_sys_sub = p_sys.add_subparsers(dest="sys_action", required=True)
    p_sys_sub.add_parser("check", help="Check for GeminiOS system component updates")
    p_sys_upd = p_sys_sub.add_parser("update", help="Update GeminiOS system components")
    p_sys_upd.add_argument("components", nargs="*", help="Specific components to update (default: all)")
    p_sys_upd.add_argument("--force", action="store_true", help="Force reinstall/update of components")

    # Repository management
    p_repo = sub.add_parser("repo", help="Manage repositories, custom repos, and Arch/AUR bridges")
    p_repo_sub = p_repo.add_subparsers(dest="repo_action", required=True)
    p_repo_sub.add_parser("list", help="List all configured repositories")
    
    p_repo_add = p_repo_sub.add_parser("add", help="Add a custom repository (GitHub user/repo or direct URL)")
    p_repo_add.add_argument("name", help="Repository identifier (e.g. community)")
    p_repo_add.add_argument("source", help="GitHub repo (user/repo) or URL to index.json")
    p_repo_add.add_argument("--branch", default="main", help="Git branch (default: main)")

    p_repo_rm = p_repo_sub.add_parser("remove", help="Remove a custom repository")
    p_repo_rm.add_argument("name", help="Repository identifier to remove")

    p_repo_en = p_repo_sub.add_parser("enable", help="Enable a repository or bridge")
    p_repo_en.add_argument("name", help="Repository or bridge (arch | aur | custom_name)")

    p_repo_dis = p_repo_sub.add_parser("disable", help="Disable a repository or bridge")
    p_repo_dis.add_argument("name", help="Repository or bridge (arch | aur | custom_name)")

    p_repo_init = p_repo_sub.add_parser("init", help="Initialize a new custom GEM repository template")
    p_repo_init.add_argument("path", help="Directory where to create the repository")
    p_repo_init.add_argument("--name", default=None, help="Repository name (default: directory name)")

    sub.add_parser("doctor", help="Check package manager health with Gemini AI")

    args = parser.parse_args()
    pm = GemPackageManager(conf_path=args.config)

    if args.command == "update":
        return pm.sync()
    if args.command == "upgrade":
        return pm.upgrade(noconfirm=args.noconfirm, system_only=args.system)
    if args.command == "install":
        return pm.install(args.packages, noconfirm=args.noconfirm)
    if args.command == "remove":
        return pm.remove(args.packages)
    if args.command == "search":
        return pm.search(args.query, use_ai=args.ai)
    if args.command == "info":
        return pm.info(args.package)
    if args.command == "list":
        return pm.list_installed(system_only=args.system)
    if args.command == "system":
        if args.sys_action == "check":
            return pm.system_check()
        if args.sys_action == "update":
            return pm.system_update(components=args.components, force=args.force)
    if args.command == "repo":
        if args.repo_action == "list":
            return pm.repo_cmd("list")
        if args.repo_action == "add":
            return pm.repo_cmd("add", target=args.name, source=args.source, branch=args.branch)
        if args.repo_action == "remove":
            return pm.repo_cmd("remove", target=args.name)
        if args.repo_action == "enable":
            return pm.repo_cmd("enable", target=args.name)
        if args.repo_action == "disable":
            return pm.repo_cmd("disable", target=args.name)
        if args.repo_action == "init":
            return pm.repo_cmd("init", target=args.path, source=args.name)
    if args.command == "doctor":
        return pm.doctor()
    return 0


if __name__ == "__main__":
    sys.exit(main())
