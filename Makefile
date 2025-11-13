.PHONY: all test cmake meson both test-cmake test-meson test-both clean format format-check tidy lint tidy-build \
        host-cmake host-meson host-both host-test-cmake host-test-meson host-test-both \
        host-format-check host-tidy host-lint sanitizers host-sanitizers analyze host-analyze \
	activity-validate log hooks-install hooks-uninstall trophy symbols-check \
	roadmap-render roadmap-sweep roadmap-validate roadmap-refresh

all: both

test: test-both

CLANG_FORMAT ?= clang-format
CLANG_TIDY ?= clang-tidy
CLANG_ANALYZER ?= scan-build
MARKDOWNLINT ?= npx --yes markdownlint-cli
MARKDOWNLINT_ARGS ?= --config .markdownlint.yaml

DISPATCH := tools/container/dispatch.sh
# Prevent accidental host execution; bypass with I_KNOW_WHAT_I_AM_DOING=1 or when CI sets CI=true.
HOST_GUARD = @if [ "$${LIBGITLEDGER_IN_CONTAINER:-0}" != "1" ] \
    && [ "$${I_KNOW_WHAT_I_AM_DOING:-0}" != "1" ] \
    && [ "$${CI:-0}" != "true" ] \
    && [ "$${CI:-0}" != "1" ]; then \
    echo "Refusing to run host target outside Docker without I_KNOW_WHAT_I_AM_DOING=1" >&2; \
    exit 1; \
fi

cmake:
	@$(DISPATCH) cmake

host-cmake:
	$(HOST_GUARD)
	cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
	cmake --build build-debug
	cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
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
	@$(DISPATCH) format-check

host-format-check:
	$(HOST_GUARD)
	tools/lint/clang_format_check.sh $(CLANG_FORMAT)

lint:
	@$(DISPATCH) lint

host-lint:
	$(HOST_GUARD)
	$(MAKE) host-format-check
	$(MAKE) host-tidy

tidy:
	@$(DISPATCH) tidy

# RUN_TIDY defaults to 1; set RUN_TIDY=0 make host-tidy when you need to bypass clang-tidy locally.
host-tidy:
	$(HOST_GUARD)
	@if [ "${RUN_TIDY:-1}" = "0" ]; then \
		echo "Skipping clang-tidy because RUN_TIDY=0"; \
	else \
		$(MAKE) tidy-build; \
	fi

tidy-build:
	tools/lint/run_clang_tidy.sh $(CLANG_TIDY)

sanitizers:
	@$(DISPATCH) sanitizers

host-sanitizers:
	$(HOST_GUARD)
	cmake -S . -B build-asan -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all" -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all"
	cmake --build build-asan
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 ctest --test-dir build-asan --output-on-failure; \
	else \
		ASAN_OPTIONS=detect_leaks=1:halt_on_error=1:detect_stack_use_after_return=1 ctest --test-dir build-asan --output-on-failure; \
	fi
	cmake -S . -B build-tsan -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_C_FLAGS="-fsanitize=thread -fno-omit-frame-pointer -O1" -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=thread -fno-omit-frame-pointer"
	cmake --build build-tsan
	TSAN_OPTIONS=halt_on_error=1 ctest --test-dir build-tsan --output-on-failure

analyze:
	@$(DISPATCH) analyze

host-analyze:
	$(HOST_GUARD)
	@an=""; \
	if command -v $(CLANG_ANALYZER) >/dev/null 2>&1; then \
		an="$(CLANG_ANALYZER)"; \
	elif command -v scan-build-18 >/dev/null 2>&1; then \
		an=scan-build-18; \
	elif command -v scan-build >/dev/null 2>&1; then \
		an=scan-build; \
	else \
		echo "scan-build (clang analyzer) is required for host-analyze"; exit 1; \
	fi; \
	cmake -S . -B build-analyze -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON; \
	"$${an}" --status-bugs -o build-analyze-scan cmake --build build-analyze

markdownlint:
	@files="$(shell git ls-files '*.md')"; if [ -z "$$files" ]; then echo "markdownlint: no markdown files found"; else $(MARKDOWNLINT) $(MARKDOWNLINT_ARGS) $$files; fi

activity-validate:
	./tools/lint/validate_activity_log.sh

log:
	@tools/log_activity_dispatch.sh

clean:
		rm -rf build build-debug build-release build-tidy build-asan build-tsan build-analyze build-analyze-scan meson-debug meson-release meson-* compile_commands.json

# Celebration: print a small trophy with current commit
trophy:
	@sha=$$(git rev-parse --short HEAD); \
	echo ""; \
	echo "   Freestanding Trophy (commit $$sha)"; \
	echo "       ___________"; \
	echo "      '._==_==_=_.'"; \
	echo "      .-\\:      /-."; \
	echo "     | (|:.     |) |"; \
	echo "      '-|:.     |-'"; \
	echo "        \\::.    /"; \
	echo "         '::. .'"; \
	echo "           ) ("; \
	echo "         _.' '._"; \
	echo "        \`\"\"\"\"\"\"\`"; \
	echo "";

# Symbol policy check: verify freestanding smoke binary pulls no forbidden symbols
symbols-check:
	$(HOST_GUARD)
	@tools/lint/check_symbols.sh

# Git hooks
hooks-install:
	@git config core.hooksPath tools/hooks
	@echo "hooks: configured core.hooksPath=tools/hooks"

hooks-uninstall:
	@git config --unset core.hooksPath || true
	@echo "hooks: unset core.hooksPath"

# Initialize submodules for fresh clones
bootstrap:
	@git submodule update --init --recursive
# Roadmap helpers
PYTHON ?= python3

.PHONY: roadmap-render roadmap-sweep roadmap-validate roadmap-refresh

roadmap-render:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "docker is required for roadmap-render" >&2; exit 1; \
	fi
	@docker run --rm -v "$(PWD)/docs:/data" minlag/mermaid-cli -i /data/ROADMAP-DAG.mmd -o /data/ROADMAP-DAG.svg

roadmap-sweep:
	@if ! command -v $(PYTHON) >/dev/null 2>&1; then \
		echo "$(PYTHON) not found; cannot run roadmap-sweep" >&2; exit 1; \
	fi
	@if [ ! -f tools/roadmap/sweep_issues.py ]; then \
		echo "tools/roadmap/sweep_issues.py not found" >&2; exit 1; \
	fi
	@$(PYTHON) tools/roadmap/sweep_issues.py

roadmap-validate:
	@if ! command -v $(PYTHON) >/dev/null 2>&1; then \
		echo "$(PYTHON) not found; cannot run roadmap-validate" >&2; exit 1; \
	fi
	@if [ ! -f tools/roadmap/validate_dag.py ]; then \
		echo "tools/roadmap/validate_dag.py not found" >&2; exit 1; \
	fi
	@$(PYTHON) tools/roadmap/validate_dag.py

roadmap-refresh:
	@$(MAKE) roadmap-validate && $(MAKE) roadmap-render
tasks-test:
	@echo "Running Python task watcher tests..."
	@python3 -m unittest -q tools/tasks/tests/test_taskwatch.py
