.PHONY: all test cmake meson both test-cmake test-meson test-both clean format format-check tidy lint tidy-build \
        host-cmake host-meson host-both host-test-cmake host-test-meson host-test-both \
        host-format-check host-tidy host-lint container-format-check container-tidy container-lint

all: both

test: test-both

CLANG_FORMAT ?= clang-format
CLANG_TIDY ?= clang-tidy

DISPATCH := tools/container/dispatch.sh
HOST_GUARD = @if [ "$${LIBGITLEDGER_IN_CONTAINER:-0}" != "1" ] && [ "$${I_KNOW_WHAT_I_AM_DOING:-0}" != "1" ]; then echo "Refusing to run host target outside Docker without I_KNOW_WHAT_I_AM_DOING=1" >&2; exit 1; fi

cmake:
	@$(DISPATCH) cmake

host-cmake:
	$(HOST_GUARD)
	cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_STANDARD=17 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
	cmake --build build-debug
	cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_STANDARD=17 -DCMAKE_C_STANDARD_REQUIRED=ON
	cmake --build build-release

meson:
	@$(DISPATCH) meson

host-meson:
	$(HOST_GUARD)
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

both:
	@$(DISPATCH) both

host-both:
	$(HOST_GUARD)
	$(MAKE) host-cmake
	$(MAKE) host-meson

test-cmake:
	@$(DISPATCH) test-cmake

host-test-cmake:
	$(HOST_GUARD)
	$(MAKE) host-cmake
	ctest --test-dir build-debug --output-on-failure
	ctest --test-dir build-release --output-on-failure

test-meson:
	@$(DISPATCH) test-meson

host-test-meson:
	$(HOST_GUARD)
	$(MAKE) host-meson
	meson test -C meson-debug --print-errorlogs
	meson test -C meson-release --print-errorlogs

test-both:
	@$(DISPATCH) test-both

host-test-both:
	$(HOST_GUARD)
	$(MAKE) host-test-cmake
	$(MAKE) host-test-meson

format:
	@files="$(shell git ls-files '*.c' '*.h')"; \
	if [ -n "$$files" ]; then \
		$(CLANG_FORMAT) -i $$files; \
	fi

format-check:
	$(MAKE) host-format-check

container-format-check:
	@$(DISPATCH) format-check

host-format-check:
	$(HOST_GUARD)
	tools/lint/clang_format_check.sh $(CLANG_FORMAT)

lint:
	$(MAKE) host-lint

container-lint:
	@$(DISPATCH) lint

host-lint:
	$(HOST_GUARD)
	$(MAKE) host-format-check
	$(MAKE) host-tidy

tidy:
	$(MAKE) host-tidy

container-tidy:
	@$(DISPATCH) tidy

host-tidy:
	$(HOST_GUARD)
	@if [ "${RUN_TIDY:-1}" = "0" ]; then \
		echo "Skipping clang-tidy because RUN_TIDY=0"; \
	else \
		$(MAKE) tidy-build; \
	fi

tidy-build:
	tools/lint/run_clang_tidy.sh $(CLANG_TIDY)

clean:
	rm -rf build build-debug build-release build-tidy meson-debug meson-release compile_commands.json
