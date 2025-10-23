FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        ninja-build \
        pkg-config \
        python3 \
        python3-pip \
        rsync \
        meson \
        gcc-14 \
        g++-14 \
        clang-18 \
        clang-format-18 \
        clang-tidy-18 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/cc cc /usr/bin/gcc-14 110 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/g++-14 110 \
    && update-alternatives --set cc /usr/bin/gcc-14 \
    && update-alternatives --set c++ /usr/bin/g++-14 \
    && ln -sf /usr/bin/clang-18 /usr/local/bin/clang \
    && ln -sf /usr/bin/clang++-18 /usr/local/bin/clang++ \
    && ln -sf /usr/bin/clang-format-18 /usr/local/bin/clang-format \
    && ln -sf /usr/bin/clang-tidy-18 /usr/local/bin/clang-tidy

WORKDIR /workspace

ENTRYPOINT []
CMD ["/bin/bash"]
