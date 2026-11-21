#!/usr/bin/env bash
# ==============================================================================
# GeminiOS 1.0 ("Spark") — Master ISO & Package Builder
# Powered by Linux · With Love, With Gemini
#
# Usage:
#   ./build.sh --docker          # Recommended: build hybrid UEFI/BIOS ISO in Docker
#   sudo ./build.sh              # Build ISO natively on a Linux host
#   ./build.sh --repo-tarballs   # Package native components for GitHub Releases (`gem`)
#   ./build.sh --qemu            # Boot built ISO in QEMU/KVM
#   ./build.sh --clean           # Clean work/ and out/ directories
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${ROOT_DIR}/work"
ROOTFS="${WORK_DIR}/rootfs"
ISO_DIR="${WORK_DIR}/iso"
OUT_DIR="${ROOT_DIR}/out"
ISO_NAME="GeminiOS-1.0.1-x86_64.iso"

log()  { printf "\033[1;34m[GeminiOS]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[GeminiOS]\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m[GeminiOS ERROR]\033[0m %s\n" "$*" >&2; exit 1; }

build_repo_tarballs() {
    log "Building release tarballs for GitHub manifest repo (geminios-repo/)..."
    mkdir -p "${OUT_DIR}/repo-releases"
    mkdir -p "${ROOT_DIR}/src/ollama-gemma/usr/share/geminios"
    echo "GeminiOS Ollama Gemma Local AI Fallback Package" > "${ROOT_DIR}/src/ollama-gemma/usr/share/geminios/ollama-gemma.info"
    tar -czf "${OUT_DIR}/repo-releases/geminios-core-1.0.0.tar.gz" -C "${ROOT_DIR}" config
    tar -czf "${OUT_DIR}/repo-releases/geminid-1.0.0.tar.gz" -C "${ROOT_DIR}/src" geminid
    tar -czf "${OUT_DIR}/repo-releases/gemini-cli-1.0.0.tar.gz" -C "${ROOT_DIR}/src/integrations" cli shell
    tar -czf "${OUT_DIR}/repo-releases/gemini-overlay-1.0.0.tar.gz" -C "${ROOT_DIR}/src/integrations" overlay dolphin clipboard
    tar -czf "${OUT_DIR}/repo-releases/gemini-oobe-1.0.0.tar.gz" -C "${ROOT_DIR}/src/integrations" oobe
    tar -czf "${OUT_DIR}/repo-releases/geminios-plasma-m3-1.0.0.tar.gz" -C "${ROOT_DIR}/src/themes" plasma-m3
    tar -czf "${OUT_DIR}/repo-releases/geminios-plymouth-1.0.0.tar.gz" -C "${ROOT_DIR}/src/themes" plymouth
    tar -czf "${OUT_DIR}/repo-releases/geminios-sddm-1.0.0.tar.gz" -C "${ROOT_DIR}/src/themes" sddm
    tar -czf "${OUT_DIR}/repo-releases/ollama-gemma-1.0.0.tar.gz" -C "${ROOT_DIR}/src/ollama-gemma" usr
    (cd "${OUT_DIR}/repo-releases" && sha256sum *.tar.gz > SHA256SUMS.txt)
    log "Release tarballs ready in ${OUT_DIR}/repo-releases/ (upload to GitHub Releases v1.0.0)."
}

run_docker_build() {
    command -v docker >/dev/null 2>&1 || die "Docker is not installed."
    log "Building GeminiOS builder image..."
    docker build -t geminios-builder:1.0.1 "${ROOT_DIR}"
    mkdir -p "${OUT_DIR}"
    log "Running privileged ISO build inside container..."
    docker run --rm --privileged \
        -v "${OUT_DIR}:/workspace/out" \
        -v geminios-pacman-cache:/var/cache/pacman/pkg \
        geminios-builder:1.0.1 --in-docker
    log "ISO build complete: ${OUT_DIR}/${ISO_NAME}"
}

run_qemu_test() {
    local iso_path="${OUT_DIR}/${ISO_NAME}"
    [[ -f "${iso_path}" ]] || die "ISO not found at ${iso_path}. Run ./build.sh --docker first."
    command -v qemu-system-x86_64 >/dev/null 2>&1 || die "qemu-system-x86_64 is not installed."
    log "Launching ${iso_path} in QEMU..."
    local kvm_flag=""
    [[ -e /dev/kvm ]] && kvm_flag="-enable-kvm"
    exec qemu-system-x86_64 \
        ${kvm_flag} \
        -m 4096 \
        -smp 4 \
        -cdrom "${iso_path}" \
        -vga virtio \
        -display gtk,gl=on \
        -boot d
}

install_geminios_stack() {
    log "Installing GeminiOS independent core, package manager, AI daemon, Panic Guard, and Material 3 Plasma 6 stack into rootfs..."

    # 1. Core OS identity & sysctl
    install -Dm644 "${ROOT_DIR}/config/os-release" "${ROOTFS}/etc/os-release"
    install -Dm644 "${ROOT_DIR}/config/geminios-release" "${ROOTFS}/etc/geminios-release"
    install -Dm644 "${ROOT_DIR}/config/sysctl.d/99-geminios.conf" "${ROOTFS}/etc/sysctl.d/99-geminios.conf"
    echo "geminios" > "${ROOTFS}/etc/hostname"
    echo "KEYMAP=us" > "${ROOTFS}/etc/vconsole.conf"

    # 2. Custom `gem` package manager + pre-seeded local manifest index + Arch/AUR bridge
    install -Dm755 "${ROOT_DIR}/src/gem/gem.py" "${ROOTFS}/usr/lib/gem/gem.py"
    install -Dm644 "${ROOT_DIR}/src/gem/arch_bridge.py" "${ROOTFS}/usr/lib/gem/arch_bridge.py"
    install -Dm644 "${ROOT_DIR}/src/gem/gem.conf" "${ROOTFS}/etc/gem/gem.conf"
    install -Dm644 "${ROOT_DIR}/src/gem/bash-completion.sh" "${ROOTFS}/usr/share/bash-completion/completions/gem"
    install -Dm644 "${ROOT_DIR}/geminios-repo/index.json" "${ROOTFS}/var/lib/gem/index.json"
    mkdir -p "${ROOTFS}/var/lib/gem/installed" "${ROOTFS}/var/cache/gem"
    ln -sf /usr/lib/gem/gem.py "${ROOTFS}/usr/bin/gem"

    # 3. `geminid` System AI Daemon + Panic Guard + System Health Watcher
    install -Dm755 "${ROOT_DIR}/src/geminid/geminid.py" "${ROOTFS}/usr/lib/geminid/geminid.py"
    install -Dm644 "${ROOT_DIR}/src/geminid/backends.py" "${ROOTFS}/usr/lib/geminid/backends.py"
    install -Dm755 "${ROOT_DIR}/src/geminid/hwcheck.py" "${ROOTFS}/usr/lib/geminid/hwcheck.py"
    install -Dm644 "${ROOT_DIR}/src/geminid/agent.py" "${ROOTFS}/usr/lib/geminid/agent.py"
    install -Dm755 "${ROOT_DIR}/src/geminid/panic_guard.py" "${ROOTFS}/usr/lib/geminid/panic_guard.py"
    install -Dm755 "${ROOT_DIR}/src/geminid/system_watcher.py" "${ROOTFS}/usr/lib/geminid/system_watcher.py"
    install -Dm644 "${ROOT_DIR}/src/geminid/geminid.conf" "${ROOTFS}/etc/geminid/geminid.conf"
    install -Dm644 "${ROOT_DIR}/src/geminid/geminid.service" "${ROOTFS}/etc/systemd/system/geminid.service"
    install -Dm644 "${ROOT_DIR}/src/geminid/geminios-panic-guard.service" "${ROOTFS}/etc/systemd/system/geminios-panic-guard.service"
    mkdir -p "${ROOTFS}/etc/systemd/system/multi-user.target.wants"
    ln -sf /etc/systemd/system/geminid.service "${ROOTFS}/etc/systemd/system/multi-user.target.wants/geminid.service"
    ln -sf /etc/systemd/system/geminios-panic-guard.service "${ROOTFS}/etc/systemd/system/multi-user.target.wants/geminios-panic-guard.service"

    # 4. OS Integrations: CLI, Doctor, Shell hooks, Overlay (Super+G), Clipboard AI (Super+Shift+G), OOBE, Dolphin menu
    install -Dm755 "${ROOT_DIR}/src/integrations/cli/gemini_cli.py" "${ROOTFS}/usr/bin/gemini"
    ln -sf /usr/bin/gemini "${ROOTFS}/usr/bin/ask"
    install -Dm755 "${ROOT_DIR}/src/integrations/cli/gemini_doctor.py" "${ROOTFS}/usr/bin/gemini-doctor"
    install -Dm644 "${ROOT_DIR}/src/integrations/shell/geminios.zsh" "${ROOTFS}/etc/profile.d/geminios.zsh"
    install -Dm644 "${ROOT_DIR}/src/integrations/shell/geminios.bash" "${ROOTFS}/etc/profile.d/geminios.bash"
    install -Dm755 "${ROOT_DIR}/src/integrations/overlay/gemini_overlay.py" "${ROOTFS}/usr/bin/gemini-overlay"
    install -Dm755 "${ROOT_DIR}/src/integrations/clipboard/gemini_clip.py" "${ROOTFS}/usr/bin/gemini-clip"
    install -Dm755 "${ROOT_DIR}/src/integrations/oobe/gemini_oobe.py" "${ROOTFS}/usr/lib/geminios/gemini_oobe.py"
    install -Dm644 "${ROOT_DIR}/src/integrations/oobe/gemini-oobe.desktop" "${ROOTFS}/etc/xdg/autostart/gemini-oobe.desktop"
    install -Dm644 "${ROOT_DIR}/src/integrations/dolphin/gemini-dolphin.desktop" \
        "${ROOTFS}/usr/share/kio/servicemenus/gemini-dolphin.desktop"

    # Autostart system health watcher in user session
    cat > "${ROOTFS}/etc/xdg/autostart/geminios-watcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GeminiOS AI System Watcher
Exec=/usr/bin/python3 /usr/lib/geminid/system_watcher.py
OnlyShowIn=KDE;
EOF

    # Desktop entries for Super+G and Super+Shift+G global shortcuts
    mkdir -p "${ROOTFS}/usr/share/applications"
    cat > "${ROOTFS}/usr/share/applications/geminios-overlay.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GeminiOS Spotlight Overlay
Comment=Global Gemini AI & Agent Mode launcher (Super+G)
Exec=/usr/bin/gemini-overlay
Icon=dialog-information
Categories=System;Utility;
EOF

    cat > "${ROOTFS}/usr/share/applications/geminios-clip.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GeminiOS Clipboard AI
Comment=Explain or fix clipboard content with Gemini (Super+Shift+G)
Exec=/usr/bin/gemini-clip
Icon=edit-paste
Categories=System;Utility;
EOF

    # 4b. GeminiOS Graphical Disk Installer (Material Design 3 Dark)
    install -Dm755 "${ROOT_DIR}/src/installer/gemini_installer.py" "${ROOTFS}/usr/bin/gemini-installer"
    install -Dm755 "${ROOT_DIR}/src/installer/install_backend.py" "${ROOTFS}/usr/lib/geminios/install_backend.py"
    install -Dm644 "${ROOT_DIR}/src/installer/geminios-installer.desktop" "${ROOTFS}/usr/share/applications/geminios-installer.desktop"
    install -Dm644 "${ROOT_DIR}/src/installer/geminios-installer.desktop" "${ROOTFS}/etc/skel/Desktop/geminios-installer.desktop"
    chmod +x "${ROOTFS}/etc/skel/Desktop/geminios-installer.desktop"
    install -Dm644 "${ROOT_DIR}/src/installer/org.geminios.installer.policy" "${ROOTFS}/usr/share/polkit-1/actions/org.geminios.installer.policy"

    # 5. Live SquashFS + OverlayFS initcpio hooks
    install -Dm644 "${ROOT_DIR}/src/live-initcpio/install/geminios-live" "${ROOTFS}/etc/initcpio/install/geminios-live"
    install -Dm644 "${ROOT_DIR}/src/live-initcpio/hooks/geminios-live" "${ROOTFS}/etc/initcpio/hooks/geminios-live"
    install -Dm644 "${ROOT_DIR}/src/live-initcpio/install/geminios-live" "${ROOTFS}/usr/lib/initcpio/install/geminios-live"
    install -Dm644 "${ROOT_DIR}/src/live-initcpio/hooks/geminios-live" "${ROOTFS}/usr/lib/initcpio/hooks/geminios-live"

    # 6. Plymouth OLED Dark Boot Splash ("GeminiOS, powered by Linux / With Love, With Gemini")
    mkdir -p "${ROOTFS}/usr/share/plymouth/themes/geminios"
    cp -r "${ROOT_DIR}/src/themes/plymouth/geminios.plymouth" "${ROOTFS}/usr/share/plymouth/themes/geminios/"
    cp -r "${ROOT_DIR}/src/themes/plymouth/geminios.script" "${ROOTFS}/usr/share/plymouth/themes/geminios/"
    cp -r "${ROOT_DIR}/src/themes/plymouth/assets/"* "${ROOTFS}/usr/share/plymouth/themes/geminios/"
    mkdir -p "${ROOTFS}/etc/plymouth"
    cat > "${ROOTFS}/etc/plymouth/plymouthd.conf" <<'EOF'
[Daemon]
Theme=geminios
ShowDelay=0
DeviceTimeout=8
EOF

    # 7. GRUB2 Dark Theme
    mkdir -p "${ROOTFS}/boot/grub/themes/geminios"
    cp -r "${ROOT_DIR}/src/themes/grub/"* "${ROOTFS}/boot/grub/themes/geminios/"

    # 8. Custom SDDM Material Design 3 Dark Login Screen (pure QtQuick)
    mkdir -p "${ROOTFS}/usr/share/sddm/themes/geminios"
    cp -r "${ROOT_DIR}/src/themes/sddm/"* "${ROOTFS}/usr/share/sddm/themes/geminios/"
    mkdir -p "${ROOTFS}/etc/sddm.conf.d" "${ROOTFS}/var/lib/sddm"
    echo -e "[Users]\nLastUser=gemini" > "${ROOTFS}/var/lib/sddm/state.conf"
    cat > "${ROOTFS}/etc/sddm.conf.d/10-geminios.conf" <<'EOF'
[Theme]
Current=geminios

[General]
DisplayServer=wayland
HaltCommand=/usr/bin/systemctl poweroff
RebootCommand=/usr/bin/systemctl reboot

[Users]
MaximumUid=60000
MinimumUid=1000
RememberLastUser=true
EOF

    mkdir -p "${ROOTFS}/etc/systemd/system/sddm.service.d"
    cat > "${ROOTFS}/etc/systemd/system/sddm.service.d/10-timeout.conf" <<'EOF'
[Service]
TimeoutStopSec=3s
EOF

    # 9. KDE Plasma 6 Google Material Design 3 Dark Theme + Splash + Konsole + Status-Bar Widget
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/color-schemes/GeminiM3Dark.colors" \
        "${ROOTFS}/usr/share/color-schemes/GeminiM3Dark.colors"
    mkdir -p "${ROOTFS}/usr/share/plasma/look-and-feel/org.geminios.material3.desktop"
    cp -r "${ROOT_DIR}/src/themes/plasma-m3/look-and-feel/org.geminios.material3.desktop/"* \
        "${ROOTFS}/usr/share/plasma/look-and-feel/org.geminios.material3.desktop/"
    mkdir -p "${ROOTFS}/usr/share/wallpapers"
    cp -r "${ROOT_DIR}/src/themes/plasma-m3/wallpapers/"* \
        "${ROOTFS}/usr/share/wallpapers/"
    mkdir -p "${ROOTFS}/usr/share/plasma/plasmoids/org.geminios.panelwidget"
    cp -r "${ROOT_DIR}/src/themes/plasma-m3/plasmoid/org.geminios.panelwidget/"* \
        "${ROOTFS}/usr/share/plasma/plasmoids/org.geminios.panelwidget/"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/konsole/GeminiM3Dark.colorscheme" \
        "${ROOTFS}/usr/share/konsole/GeminiM3Dark.colorscheme"

    # Install Google G + Gemini Star launcher icons
    mkdir -p "${ROOTFS}/usr/share/icons/hicolor/scalable/apps" "${ROOTFS}/usr/share/icons/hicolor/64x64/apps"
    install -Dm644 "${ROOT_DIR}/src/themes/logo/geminios-logo.svg" "${ROOTFS}/usr/share/icons/hicolor/scalable/apps/geminios-launcher.svg"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/icons/geminios-launcher.png" "${ROOTFS}/usr/share/icons/hicolor/64x64/apps/geminios-launcher.png"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/icons/geminios-launcher.png" "${ROOTFS}/usr/share/icons/geminios-launcher.png"

    # Install fast systemd shutdown timeouts
    mkdir -p "${ROOTFS}/etc/systemd/system.conf.d" "${ROOTFS}/etc/systemd/user.conf.d"
    install -Dm644 "${ROOT_DIR}/config/systemd/system.conf.d/10-geminios-shutdown.conf" \
        "${ROOTFS}/etc/systemd/system.conf.d/10-geminios-shutdown.conf"
    install -Dm644 "${ROOT_DIR}/config/systemd/user.conf.d/10-geminios-shutdown.conf" \
        "${ROOTFS}/etc/systemd/user.conf.d/10-geminios-shutdown.conf"

    # Full skeleton user config (/etc/skel) so Plasma 6 boots straight into M3 Dark with zero default KDE clutter
    mkdir -p "${ROOTFS}/etc/skel/.config/gtk-3.0" "${ROOTFS}/etc/skel/.config/gtk-4.0" "${ROOTFS}/etc/skel/.local/share/konsole"
    install -Dm644 "${ROOT_DIR}/src/integrations/shell/skel.zshrc" "${ROOTFS}/etc/skel/.zshrc"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/kwin/kwinrc" "${ROOTFS}/etc/skel/.config/kwinrc"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/breezerc" "${ROOTFS}/etc/skel/.config/breezerc"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/kglobalshortcutsrc" "${ROOTFS}/etc/skel/.config/kglobalshortcutsrc"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/plasma-org.kde.plasma.desktop-appletsrc" \
        "${ROOTFS}/etc/skel/.config/plasma-org.kde.plasma.desktop-appletsrc"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/gtk/gtk-m3-dark.css" "${ROOTFS}/etc/skel/.config/gtk-3.0/gtk.css"
    install -Dm644 "${ROOT_DIR}/src/themes/plasma-m3/gtk/gtk-m3-dark.css" "${ROOTFS}/etc/skel/.config/gtk-4.0/gtk.css"

    cat > "${ROOTFS}/etc/skel/.config/ksplashrc" <<'EOF'
[KSplash]
Engine=KSplashQML
Theme=org.geminios.material3.desktop
EOF

    cat > "${ROOTFS}/etc/skel/.config/plasmarc" <<'EOF'
[Theme]
name=breeze-dark
EOF

    cat > "${ROOTFS}/etc/skel/.config/kdeglobals" <<'EOF'
[General]
ColorScheme=GeminiM3Dark
font=Roboto,10,-1,5,400,0,0,0,0,0
fixed=JetBrains Mono,10,-1,5,400,0,0,0,0,0

[KDE]
LookAndFeelPackage=org.geminios.material3.desktop
widgetStyle=Breeze
EOF

    cat > "${ROOTFS}/etc/skel/.local/share/konsole/GeminiM3Dark.profile" <<'EOF'
[Appearance]
ColorScheme=GeminiM3Dark
Font=JetBrains Mono,10,-1,5,400,0,0,0,0,0

[General]
Command=/bin/zsh
Name=GeminiOS M3 Dark
Parent=FALLBACK/
EOF

    cat > "${ROOTFS}/etc/skel/.config/konsolerc" <<'EOF'
[Desktop Entry]
DefaultProfile=GeminiM3Dark.profile
EOF
}

build_iso_native() {
    [[ "${EUID}" -eq 0 ]] || die "Native ISO build requires root. Run with sudo or use ./build.sh --docker"
    rm -rf "${WORK_DIR}"
    mkdir -p "${ROOTFS}" "${ISO_DIR}/live" "${ISO_DIR}/boot/grub/themes" "${OUT_DIR}"

    log "Optimizing pacman parallel downloads..."
    sed -i 's/^#ParallelDownloads = .*/ParallelDownloads = 10/' /etc/pacman.conf
    sed -i 's/^ParallelDownloads = .*/ParallelDownloads = 10/' /etc/pacman.conf

    log "Bootstrapping independent glibc + Linux + base-devel + KDE Plasma 6 rootfs (using host package cache)..."
    pacstrap -c -P "${ROOTFS}" \
        base base-devel pacman archlinux-keyring linux linux-firmware glibc systemd systemd-sysvcompat \
        iptables mkinitcpio pipewire-jack qt6-multimedia-ffmpeg \
        networkmanager iwd bluez pipewire pipewire-pulse wireplumber \
        sudo zsh bash git curl wget python python-pyqt6 wl-clipboard libnotify \
        wayland xorg-xwayland mesa \
        plasma-desktop plasma-workspace kwin sddm dolphin konsole kate \
        plasma-nm plasma-pa powerdevil bluedevil breeze breeze-gtk kde-gtk-config \
        noto-fonts noto-fonts-emoji ttf-roboto ttf-jetbrains-mono \
        plymouth grub efibootmgr parted dosfstools e2fsprogs btrfs-progs rsync squashfs-tools arch-install-scripts

    # Ensure pacman config, mirrorlist and keys are definitely present in rootfs
    cp -f /etc/pacman.conf "${ROOTFS}/etc/pacman.conf"
    mkdir -p "${ROOTFS}/etc/pacman.d"
    cp -f /etc/pacman.d/mirrorlist "${ROOTFS}/etc/pacman.d/mirrorlist"
    [[ -d /etc/pacman.d/gnupg ]] && cp -a /etc/pacman.d/gnupg "${ROOTFS}/etc/pacman.d/"

    install_geminios_stack

    log "Configuring default live user ('gemini' / password 'gemini'), Arch keyring, services, and Live+Plymouth initramfs..."
    arch-chroot "${ROOTFS}" /bin/bash -euo pipefail <<'CHROOT'
# Ensure Arch keyring is fully valid
pacman-key --init || true
pacman-key --populate archlinux || true

useradd -m -G wheel,audio,video,storage -s /bin/zsh gemini || true
echo "gemini:gemini" | chpasswd
echo "root:gemini" | chpasswd
echo "%wheel ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/10-wheel
chmod 440 /etc/sudoers.d/10-wheel
chown -R gemini:gemini /home/gemini || true

systemctl enable NetworkManager.service
systemctl enable sddm.service
systemctl enable geminid.service
systemctl enable geminios-panic-guard.service

# Configure universal Live SquashFS + Plymouth initramfs (no autodetect so ISO boots on any hardware/QEMU)
cat > /etc/mkinitcpio.conf <<'MKCONF'
MODULES=(squashfs overlay loop isofs sr_mod sd_mod virtio_blk virtio_scsi ahci)
BINARIES=()
FILES=()
HOOKS=(base udev plymouth modconf kms keyboard keymap consolefont block filesystems geminios-live)
MKCONF

mkinitcpio -P
CHROOT

    log "Compressing rootfs into SquashFS (fast parallel zstd)..."
    mksquashfs "${ROOTFS}" "${ISO_DIR}/live/filesystem.squashfs" -comp zstd -Xcompression-level 6 -processors "$(nproc)" -noappend

    log "Copying kernel, initramfs, and configuring GRUB2 dark boot menu..."
    cp "${ROOTFS}/boot/vmlinuz-linux" "${ISO_DIR}/boot/vmlinuz-geminios"
    cp "${ROOTFS}/boot/initramfs-linux.img" "${ISO_DIR}/boot/initramfs-geminios.img"
    mkdir -p "${ISO_DIR}/boot/grub/themes/geminios"
    cp -r "${ROOT_DIR}/src/themes/grub/"* "${ISO_DIR}/boot/grub/themes/geminios/"

    cat > "${ISO_DIR}/boot/grub/grub.cfg" <<'EOF'
set timeout=5
set default=0
insmod part_gpt
insmod part_msdos
insmod all_video
insmod gfxterm
insmod png
insmod jpeg
set gfxmode=auto
terminal_output gfxterm
set theme=/boot/grub/themes/geminios/theme.txt

menuentry "Start GeminiOS 1.0.1 (Spark) - Material Design 3 Dark" {
    linux /boot/vmlinuz-geminios geminios_label=GEMINIOS_1_0_1 quiet splash loglevel=3 rd.udev.log_priority=3 vt.global_cursor_default=0
    initrd /boot/initramfs-geminios.img
}

menuentry "Start GeminiOS 1.0.1 (Safe Graphics / Verbose)" {
    linux /boot/vmlinuz-geminios geminios_label=GEMINIOS_1_0_1 nomodeset
    initrd /boot/initramfs-geminios.img
}
EOF

    log "Generating hybrid UEFI/BIOS bootable ISO (${OUT_DIR}/${ISO_NAME})..."
    grub-mkrescue -o "${OUT_DIR}/${ISO_NAME}" "${ISO_DIR}" -- -volid "GEMINIOS_1_0_1"
    (cd "${OUT_DIR}" && sha256sum "${ISO_NAME}" > "${ISO_NAME}.sha256")
    log "Done! ISO built at ${OUT_DIR}/${ISO_NAME}"
}

case "${1:-}" in
    --docker)
        run_docker_build
        ;;
    --in-docker|"")
        build_iso_native
        ;;
    --repo-tarballs)
        build_repo_tarballs
        ;;
    --qemu)
        run_qemu_test
        ;;
    --clean)
        rm -rf "${WORK_DIR}" "${OUT_DIR}"
        log "Cleaned work/ and out/."
        ;;
    *)
        echo "Usage: $0 [--docker | --repo-tarballs | --qemu | --clean]"
        exit 1
        ;;
esac
