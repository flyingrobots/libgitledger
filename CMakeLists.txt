cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C ASM)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(GITLEDGER_VENDOR_LIBGIT2 "Build against a vendored libgit2 copy (placeholder)" OFF)
option(GITLEDGER_WITH_CROARING "Enable CRoaring integration (placeholder)" OFF)
option(GITLEDGER_WITH_BLAKE3 "Enable BLAKE3 support (placeholder)" OFF)
set(GITLEDGER_WITH_LIBGIT2 "AUTO" CACHE STRING "Use libgit2 (values: AUTO, ON, OFF)")
set_property(CACHE GITLEDGER_WITH_LIBGIT2 PROPERTY STRINGS AUTO ON OFF)
string(TOUPPER "${GITLEDGER_WITH_LIBGIT2}" GITLEDGER_WITH_LIBGIT2_MODE)

if(GITLEDGER_WITH_CROARING)
    message(STATUS "CRoaring support is not implemented yet; continuing without it.")
endif()

if(GITLEDGER_WITH_BLAKE3)
    message(STATUS "BLAKE3 support is not implemented yet; continuing without it.")
endif()

if(MSVC)
    set(PROJECT_WARNING_FLAGS /W4 /WX /we4244 /we4267 /we4456 /we4457 /we4458 /we4459)
else()

include(CheckCCompilerFlag)
option(GITLEDGER_USE_NOSTDLIB "Link freestanding smoke executable with -nostdlib (non-MSVC)" OFF)
# Project policy: strict warnings, C99, no fun, visibility hidden.
set(PROJECT_WARNING_FLAGS -Wall -Wextra -Werror -pedantic -Wshadow -Wconversion -fvisibility=hidden -std=c99)
check_c_compiler_flag("-Wno-fun" COMPILER_SUPPORTS_WNOFUN)
if(COMPILER_SUPPORTS_WNOFUN)
  list(APPEND PROJECT_WARNING_FLAGS -Wno-fun)
endif()

endif()

set(LIBGITLEDGER_SOURCES
    libgitledger/core/context.c
    libgitledger/core/domain/gitledger.c
    libgitledger/core/domain/error.c
    src/version.c
)

set(LIBGITLEDGER_HEADERS
    libgitledger/include/gitledger/gitledger.h
    include/gitledger/version.h
    include/gitledger/context.h
    include/gitledger/error.h
    include/gitledger/export.h
)

add_library(gitledger STATIC ${LIBGITLEDGER_SOURCES} ${LIBGITLEDGER_HEADERS})
target_compile_options(gitledger PRIVATE ${PROJECT_WARNING_FLAGS})
target_compile_definitions(gitledger PRIVATE GITLEDGER_BUILD=1)
function(add_nostdlib target)
  if(GITLEDGER_USE_NOSTDLIB AND NOT MSVC)
    # Link without the system CRT/stdlib; ASM is already enabled project-wide.
    target_sources(${target} PRIVATE crt/linux/x86_64/crt0.S)
    target_link_options(${target} PRIVATE -nostdlib)
  endif()
endfunction()
if(NOT MSVC)
  # Keep library pure/freestanding from the linker perspective.
  target_link_options(gitledger PRIVATE -nostdlib)
endif()

if(GITLEDGER_VENDOR_LIBGIT2)
    message(FATAL_ERROR "Vendored libgit2 support is not implemented yet.\n"
                           "Install libgit2 on your system or rerun with -DGITLEDGER_VENDOR_LIBGIT2=OFF to continue.")
endif()

set(GITLEDGER_LIBGIT2_TARGET "")

if(NOT GITLEDGER_WITH_LIBGIT2_MODE STREQUAL "OFF")
    find_package(LibGit2 QUIET)
    if(LibGit2_FOUND)
        set(GITLEDGER_LIBGIT2_TARGET LibGit2::LibGit2)
    else()
        find_package(PkgConfig QUIET)
        if(PKG_CONFIG_FOUND)
            pkg_check_modules(LIBGIT2 IMPORTED_TARGET libgit2)
            if(LIBGIT2_FOUND)
                set(GITLEDGER_LIBGIT2_TARGET PkgConfig::LIBGIT2)
            endif()
        endif()
    endif()

    if(GITLEDGER_LIBGIT2_TARGET STREQUAL "")
        if(GITLEDGER_WITH_LIBGIT2_MODE STREQUAL "ON")
            message(FATAL_ERROR "libgit2 development files were not found.\n"
                               "Install libgit2 and pkg-config using one of:\n"
                               "  sudo apt-get install libgit2-dev pkg-config\n"
                               "  brew install libgit2 pkg-config\n"
                               "  choco install libgit2 pkgconfiglite\n"
                               "Then rerun CMake, or pass -DGITLEDGER_WITH_LIBGIT2=OFF to continue without libgit2.")
        else()
            message(STATUS "libgit2 not found; continuing without libgit2 integration."
                           " Set -DGITLEDGER_WITH_LIBGIT2=ON after installing libgit2 to enable it.")
        endif()
    else()
        message(STATUS "libgit2 dependency detected via ${GITLEDGER_LIBGIT2_TARGET}.")
        target_link_libraries(gitledger PRIVATE ${GITLEDGER_LIBGIT2_TARGET})
        target_compile_definitions(gitledger PRIVATE GITLEDGER_HAVE_LIBGIT2=1)
    endif()
else()
    message(STATUS "libgit2 support disabled via -DGITLEDGER_WITH_LIBGIT2=OFF")
endif()

target_include_directories(gitledger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/libgitledger/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

add_executable(gitledger_version_test tests/version_test.c)
target_compile_options(gitledger_version_test PRIVATE ${PROJECT_WARNING_FLAGS})
target_link_libraries(gitledger_version_test PRIVATE gitledger)

add_executable(gitledger_tests libgitledger/tests/main.c)
target_compile_options(gitledger_tests PRIVATE ${PROJECT_WARNING_FLAGS})
target_link_libraries(gitledger_tests PRIVATE gitledger)

add_executable(mg-ledger libgitledger/cli/mg-ledger.c)
target_compile_options(mg-ledger PRIVATE ${PROJECT_WARNING_FLAGS})
target_link_libraries(mg-ledger PRIVATE gitledger)

add_executable(gitledger_error_test tests/error_test.c)
target_compile_options(gitledger_error_test PRIVATE ${PROJECT_WARNING_FLAGS})
target_link_libraries(gitledger_error_test PRIVATE gitledger)

include(CTest)
if(BUILD_TESTING)
    add_test(NAME version COMMAND gitledger_version_test)
    add_test(NAME gitledger_cli_smoke COMMAND gitledger_tests)
    add_test(NAME error COMMAND gitledger_error_test)

    # Failing-first acceptance test for Issue #51:
    # Expect a CMake target named 'doxygen' to exist and be buildable.
    # This will initially fail until the target is implemented.
    add_test(
        NAME docs_doxygen_target
        COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target doxygen
    )
endif()

# -----------------------------------------------------------------------------
# Documentation (Issue #51): Doxygen configuration and target
# -----------------------------------------------------------------------------
find_package(Doxygen QUIET)

set(GL_DOXY_INPUT "${CMAKE_SOURCE_DIR}/docs/Doxyfile")

if (DOXYGEN_FOUND)
    message(STATUS "Doxygen found: enabling 'doxygen' target")
    # Configure environment for Doxygen: allow CMake variable expansion in file
    # by generating a build-local copy with paths substituted.
    set(GL_DOXY_OUT_DIR "${CMAKE_BINARY_DIR}/docs/api")
    set(GL_DOXY_CONFIG "${CMAKE_BINARY_DIR}/Doxyfile")
    configure_file("${GL_DOXY_INPUT}" "${GL_DOXY_CONFIG}" @ONLY)

    add_custom_target(
        doxygen
        COMMAND ${DOXYGEN_EXECUTABLE} "${GL_DOXY_CONFIG}"
        BYPRODUCTS "${GL_DOXY_OUT_DIR}/html/index.html"
        WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
        COMMENT "Generating API documentation with Doxygen"
        VERBATIM
    )

    if(BUILD_TESTING)
        # Verify HTML output exists after building the target.
        add_test(
            NAME docs_doxygen_output
            COMMAND ${CMAKE_COMMAND}
                    -DGL_DOC_OUT=${CMAKE_BINARY_DIR}/docs/api/html/index.html
                    -P ${CMAKE_SOURCE_DIR}/cmake/verify_doxygen.cmake
        )
    endif()
else()
    message(STATUS "Doxygen not found: defining stub 'doxygen' target (no-op)")
    add_custom_target(
        doxygen
        COMMAND ${CMAKE_COMMAND} -E echo "Doxygen not found; skipping docs generation"
    )
endif()

# Freestanding smoke executable (only when explicitly enabled and non-MSVC)
if(GITLEDGER_USE_NOSTDLIB AND NOT MSVC)
  add_executable(gitledger_ffs_smoke tests/ffs_smoke.c)
  target_compile_options(gitledger_ffs_smoke PRIVATE ${PROJECT_WARNING_FLAGS})
  target_link_libraries(gitledger_ffs_smoke PRIVATE gitledger)
  add_nostdlib(gitledger_ffs_smoke)
  # Hardened distros enable stack protector and PIE by default; disable for freestanding.
  target_compile_options(gitledger PRIVATE -fno-stack-protector -fno-builtin -fno-pie)
  target_compile_options(gitledger_ffs_smoke PRIVATE -fno-stack-protector -fno-builtin -fno-pie)
  target_link_options(gitledger_ffs_smoke PRIVATE -no-pie)
  if(BUILD_TESTING)
    add_test(NAME ffs_smoke COMMAND gitledger_ffs_smoke)
  endif()
endif()
