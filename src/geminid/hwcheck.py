#!/usr/bin/env python3
"""
GeminiOS Hardware Capability Checker & Automatic Gemma Fallback Installer (`hwcheck.py`)
Detects RAM, CPU cores, AVX2 support, and GPU VRAM, determines whether the machine
can comfortably run local Gemma models via Ollama, and pulls the optimal model on consent.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


def detect_ram_gb() -> float:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


def detect_cpu_info() -> Dict:
    cores = os.cpu_count() or 1
    avx2 = False
    model = "Unknown CPU"
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("model name") and model == "Unknown CPU":
                model = line.split(":", 1)[1].strip()
            if line.startswith("flags") and "avx2" in line.lower():
                avx2 = True
    except Exception:
        pass
    return {"model": model, "cores": cores, "avx2": avx2}


def detect_gpu_vram_gb() -> Dict:
    if shutil.which("nvidia-smi"):
        try:
            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                line = proc.stdout.strip().splitlines()[0]
                name, vram_mb = [p.strip() for p in line.split(",", 1)]
                return {"vendor": "NVIDIA", "name": name, "vram_gb": round(float(vram_mb) / 1024.0, 2)}
        except Exception:
            pass

    for vram_file in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        try:
            vram_bytes = int(vram_file.read_text(encoding="utf-8").strip())
            if vram_bytes > 0:
                return {"vendor": "AMD", "name": "AMD Radeon GPU", "vram_gb": round(vram_bytes / (1024**3), 2)}
        except Exception:
            pass

    return {"vendor": "Integrated/CPU", "name": "CPU Inference", "vram_gb": 0.0}


def evaluate_gemma_capability() -> Dict:
    ram_gb = detect_ram_gb()
    cpu = detect_cpu_info()
    gpu = detect_gpu_vram_gb()
    vram_gb = gpu["vram_gb"]

    if vram_gb >= 10.0 or ram_gb >= 24.0:
        recommended = "gemma3:12b"
        capable = True
        tier = "high"
        note = "High-memory system detected: gemma3:12b runs smoothly."
    elif vram_gb >= 4.0 or (ram_gb >= 7.5 and cpu["cores"] >= 4):
        recommended = "gemma3:4b"
        capable = True
        tier = "medium"
        note = "Balanced hardware detected: gemma3:4b recommended for offline fallback."
    elif ram_gb >= 3.2:
        recommended = "gemma3:1b"
        capable = True
        tier = "light"
        note = "4 GB class system detected: gemma3:1b fits comfortably for offline fallback."
    else:
        recommended = None
        capable = False
        tier = "unsupported"
        note = "Less than 3.2 GB usable RAM detected: local Gemma fallback is not recommended."

    return {
        "capable": capable,
        "tier": tier,
        "recommended_model": recommended,
        "note": note,
        "ram_gb": ram_gb,
        "cpu": cpu,
        "gpu": gpu,
        "ollama_installed": shutil.which("ollama") is not None,
    }


def install_ollama_and_pull_gemma(model: Optional[str] = None) -> Dict:
    report = evaluate_gemma_capability()
    if not report["capable"]:
        return {"ok": False, "error": report["note"], "report": report}

    target_model = model if (model and model != "auto") else report["recommended_model"]
    if not shutil.which("ollama"):
        print("[geminid:hwcheck] Installing Ollama runtime for local Gemma fallback...")
        rc = subprocess.run(
            ["/bin/bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            check=False,
        ).returncode
        if rc != 0:
            return {"ok": False, "error": "Failed to install Ollama.", "report": report}

    subprocess.run(["systemctl", "enable", "--now", "ollama.service"], check=False)
    print(f"[geminid:hwcheck] Pulling local fallback model `{target_model}`...")
    rc = subprocess.run(["ollama", "pull", target_model], check=False).returncode
    if rc != 0:
        return {"ok": False, "error": f"Failed to pull `{target_model}` via Ollama.", "report": report}

    return {"ok": True, "model": target_model, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="GeminiOS Hardware Check & Gemma Auto-Downloader")
    parser.add_argument("--json", action="store_true", help="Output JSON hardware report")
    parser.add_argument("--auto-install", action="store_true", help="Install Ollama & pull optimal Gemma model")
    parser.add_argument("--model", default="auto", help="Override Gemma model tag")
    args = parser.parse_args()

    if args.auto_install:
        result = install_ollama_and_pull_gemma(args.model)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    report = evaluate_gemma_capability()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"RAM: {report['ram_gb']} GB | CPU: {report['cpu']['model']} ({report['cpu']['cores']} cores, AVX2={report['cpu']['avx2']})")
        print(f"GPU: {report['gpu']['vendor']} {report['gpu']['name']} ({report['gpu']['vram_gb']} GB VRAM)")
        print(f"Capable: {report['capable']} | Recommended Gemma: {report['recommended_model']} | {report['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
