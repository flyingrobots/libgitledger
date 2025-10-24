FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.10ubuntu1 \
        ca-certificates=20240203 \
        cmake=3.28.3-1build7 \
        git=1:2.43.0-1ubuntu7.3 \
        ninja-build=1.11.1-2 \
        pkg-config=1.8.1-2build1 \
        python3=3.12.3-0ubuntu2 \
        python3-pip=24.0+dfsg-1ubuntu1.3 \
        rsync=3.2.7-1ubuntu1.2 \
        meson=1.3.2-1ubuntu1 \
        gcc-14=14.2.0-4ubuntu2~24.04 \
        g++-14=14.2.0-4ubuntu2~24.04 \
        clang-18=1:18.1.3-1ubuntu1 \
        clang-format-18=1:18.1.3-1ubuntu1 \
        clang-tidy-18=1:18.1.3-1ubuntu1 \
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
