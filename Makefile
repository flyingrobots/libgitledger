.PHONY: cmake meson both test-cmake test-meson test-both clean format format-check tidy lint tidy-build

CLANG_FORMAT ?= clang-format
CLANG_TIDY ?= clang-tidy

cmake:
	cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
	cmake --build build-debug
	cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
	cmake --build build-release

meson:
	@if [ -d meson-debug ]; then \
		meson setup meson-debug --buildtype debugoptimized --reconfigure; \
	else \
		meson setup meson-debug --buildtype debugoptimized; \
	fi
	meson compile -C meson-debug
	@if [ -d meson-release ]; then \
		meson setup meson-release --buildtype release --reconfigure; \
	else \
		meson setup meson-release --buildtype release; \
	fi
	meson compile -C meson-release

both: cmake meson

test-cmake: cmake
	ctest --test-dir build-debug --output-on-failure
	ctest --test-dir build-release --output-on-failure

test-meson: meson
	meson test -C meson-debug --print-errorlogs
	meson test -C meson-release --print-errorlogs

test-both: test-cmake test-meson

format:
	@files="$(shell git ls-files '*.c' '*.h')"; \
	if [ -n "$$files" ]; then \
		$(CLANG_FORMAT) -i $$files; \
	fi

format-check:
	tools/lint/clang_format_check.sh $(CLANG_FORMAT)

lint: format-check tidy

 tidy: tidy-build

tidy-build:
	tools/lint/run_clang_tidy.sh $(CLANG_TIDY)

clean:
	rm -rf build build-debug build-release build-tidy meson-debug meson-release compile_commands.json
