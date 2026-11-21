#!/usr/bin/env python3
"""Automated verification suite for GeminiOS 1.0 source tree."""

import json
import py_compile
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_python_syntax():
    py_files = sorted(ROOT.rglob("*.py"))
    assert len(py_files) >= 11, f"Expected >=11 Python files, found {len(py_files)}"
    for p in py_files:
        py_compile.compile(str(p), doraise=True)
    print(f"[PASS] Python syntax valid across {len(py_files)} files.")


def check_shell_syntax():
    for sh in [
        ROOT / "build.sh",
        ROOT / "src/gem/bash-completion.sh",
        ROOT / "src/integrations/shell/geminios.bash",
        ROOT / "src/live-initcpio/install/geminios-live",
    ]:
        if sys.platform == "win32":
            p = sh.resolve()
            drive = p.drive.rstrip(":").lower()
            wsl_path = f"/mnt/{drive}{p.as_posix()[2:]}"
            subprocess.run(["bash", "-c", f"bash -n '{wsl_path}'"], check=True)
        else:
            subprocess.run(["bash", "-n", str(sh)], check=True)
    print("[PASS] Bash & initcpio scripts syntax valid.")


def check_configs_and_manifests():
    for conf in [ROOT / "src/gem/gem.conf", ROOT / "src/geminid/geminid.conf"]:
        data = tomllib.loads(conf.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and len(data) > 0

    idx = json.loads((ROOT / "geminios-repo/index.json").read_text(encoding="utf-8"))
    pkgs = idx.get("packages", {})
    assert len(pkgs) >= 8
    for name, meta in pkgs.items():
        manifest_path = ROOT / "geminios-repo" / meta["manifest"]
        assert manifest_path.exists(), f"Missing manifest {manifest_path}"
        m = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        assert m["package"]["name"] == name

    # Verify package manager protected blacklist & base package preservation
    sys.path.insert(0, str(ROOT / "src/gem"))
    import gem
    assert "etc/resolv.conf" in gem.PROTECTED_SYSTEM_PATHS
    assert "etc/passwd" in gem.PROTECTED_SYSTEM_PATHS
    assert "etc/shells" in gem.PROTECTED_SYSTEM_PATHS
    assert "filesystem" in gem.SYSTEM_BASE_PACKAGES
    assert "glibc" in gem.SYSTEM_BASE_PACKAGES

    print(f"[PASS] Configs, {len(pkgs)} GitHub package manifests, and gem safety barriers valid.")


def check_agent_hwcheck_and_panic_guard():
    sys.path.insert(0, str(ROOT / "src/geminid"))
    import agent
    import hwcheck
    import panic_guard

    assert agent.classify_risk("ls -la") == "safe"
    assert agent.classify_risk("sudo systemctl restart NetworkManager") == "elevated"
    assert agent.classify_risk("rm -rf /") == "destructive"

    plan = agent.extract_json_plan('{"summary":"Test","steps":[{"cmd":"uname -a","reason":"check kernel"}]}')
    assert len(plan["steps"]) == 1 and plan["steps"][0]["risk"] == "safe"

    hw = hwcheck.evaluate_gemma_capability()
    assert "ram_gb" in hw and "capable" in hw and "recommended_model" in hw

    # Verify every forbidden phrase triggers PanicSequenceDetector
    for phrase in panic_guard.FORBIDDEN_PHRASES:
        det = panic_guard.PanicSequenceDetector()
        codes = panic_guard.phrase_to_keycodes(phrase)
        matched = None
        for code in codes:
            matched = det.feed(code)
        assert matched == phrase, f"Panic detector failed to match '{phrase}'"

    # Verify numpad 67 triggers too
    det_kp = panic_guard.PanicSequenceDetector()
    det_kp.feed(panic_guard.KEY_KP6)
    assert det_kp.feed(panic_guard.KEY_KP7) == "67"

    print(f"[PASS] Agent, hardware checker, and Panic Guard (all {len(panic_guard.FORBIDDEN_PHRASES)} phrases + numpad) valid.")


def check_theme_assets():
    required = [
        "src/themes/plymouth/geminios.plymouth",
        "src/themes/plymouth/geminios.script",
        "src/themes/plymouth/assets/google_gemini_logo.png",
        "src/themes/plymouth/assets/footer_text.png",
        "src/themes/plymouth/assets/spinner_00.png",
        "src/themes/plymouth/assets/spinner_23.png",
        "src/themes/grub/theme.txt",
        "src/themes/grub/assets/background.png",
        "src/themes/sddm/Main.qml",
        "src/themes/sddm/assets/background.png",
        "src/themes/plasma-m3/color-schemes/GeminiM3Dark.colors",
        "src/themes/plasma-m3/desktoptheme/GeminiM3/metadata.json",
        "src/themes/plasma-m3/desktoptheme/GeminiM3/widgets/panel-background.svg",
        "src/themes/plasma-m3/desktoptheme/GeminiM3/widgets/background.svg",
        "src/themes/plasma-m3/desktoptheme/GeminiM3/widgets/tasks.svg",
        "src/themes/plasma-m3/plasmoid/org.geminios.panelwidget/contents/ui/main.qml",
        "src/themes/plasma-m3/wallpapers/GeminiM3Dark/contents/images/1920x1080.png",
        "src/live-initcpio/install/geminios-live",
        "src/live-initcpio/hooks/geminios-live",
        "src/integrations/activation/activation_watermark.py",
        "src/themes/plasma-m3/icons/geminios-installer.svg",
        "src/themes/plasma-m3/icons/gemini-spotlight.svg",
        "src/themes/plasma-m3/icons/gemini-clip.svg",
        "src/themes/plasma-m3/icons/gemini-oobe.svg",
    ]
    for rel in required:
        p = ROOT / rel
        assert p.exists() and p.stat().st_size > 0, f"Missing or empty asset: {rel}"
    print(f"[PASS] All {len(required)} core theme, live-boot, and visual assets verified.")


if __name__ == "__main__":
    check_python_syntax()
    check_shell_syntax()
    check_configs_and_manifests()
    check_agent_hwcheck_and_panic_guard()
    check_theme_assets()
    print("\nALL GEMINIOS 1.0 VERIFICATION CHECKS PASSED.")
