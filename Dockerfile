# GeminiOS 1.0.1 Reproducible ISO Builder Container
FROM archlinux:latest

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    GEMINIOS_VERSION=1.0.1

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm --needed \
        base-devel \
        arch-install-scripts \
        squashfs-tools \
        libisoburn \
        dosfstools \
        mtools \
        grub \
        efibootmgr \
        python \
        python-pip \
        git \
        curl \
        tar \
        zstd \
        gzip && \
    pacman -Scc --noconfirm

WORKDIR /workspace
COPY . /workspace
RUN chmod +x /workspace/build.sh

ENTRYPOINT ["/workspace/build.sh"]
CMD ["--in-docker"]
