.PHONY: cmake meson both test-cmake test-meson test-both clean

cmake:
	cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug
	cmake --build build-debug
	cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
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
	ctest --test-dir build-debug
	ctest --test-dir build-release

test-meson: meson
	meson test -C meson-debug
	meson test -C meson-release

test-both: test-cmake test-meson

clean:
	rm -rf build-debug build-release meson-debug meson-release compile_commands.json
