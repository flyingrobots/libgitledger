cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(GITLEDGER_VENDOR_LIBGIT2 "Build against a vendored libgit2 copy (placeholder)" OFF)
option(GITLEDGER_WITH_CROARING "Enable CRoaring integration (placeholder)" OFF)
option(GITLEDGER_WITH_BLAKE3 "Enable BLAKE3 support (placeholder)" OFF)

if(GITLEDGER_WITH_CROARING)
    message(STATUS "CRoaring support is not implemented yet; continuing without it.")
endif()

if(GITLEDGER_WITH_BLAKE3)
    message(STATUS "BLAKE3 support is not implemented yet; continuing without it.")
endif()

if(MSVC)
    set(PROJECT_WARNING_FLAGS /W4 /WX /we4244 /we4267 /we4456 /we4457 /we4458 /we4459)
else()
    # Keep Unix builds strict and hide unintended symbol exports.
    set(PROJECT_WARNING_FLAGS -Wall -Wextra -Werror -Wpedantic -Wshadow -Wconversion -fvisibility=hidden)
endif()

set(LIBGITLEDGER_SOURCES
    libgitledger/core/domain/gitledger.c
    src/version.c
)

set(LIBGITLEDGER_HEADERS
    libgitledger/include/gitledger/gitledger.h
    include/libgitledger/version.h
)

add_library(gitledger STATIC ${LIBGITLEDGER_SOURCES} ${LIBGITLEDGER_HEADERS})
target_compile_options(gitledger PRIVATE ${PROJECT_WARNING_FLAGS})

if(GITLEDGER_VENDOR_LIBGIT2)
    message(FATAL_ERROR "Vendored libgit2 support is not implemented yet. Install libgit2 or configure without -DGITLEDGER_VENDOR_LIBGIT2=ON.")
endif()

set(GITLEDGER_LIBGIT2_TARGET "")

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
    message(FATAL_ERROR "libgit2 development files were not found. Install libgit2 and pkg-config (e.g. 'sudo apt-get install libgit2-dev pkg-config', 'brew install libgit2 pkg-config', or 'choco install libgit2 pkgconfiglite') and reconfigure.")
endif()

target_link_libraries(gitledger PUBLIC ${GITLEDGER_LIBGIT2_TARGET})
target_compile_definitions(gitledger PUBLIC GITLEDGER_HAVE_LIBGIT2=1)

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

include(CTest)
if(BUILD_TESTING)
    add_test(NAME version COMMAND gitledger_version_test)
    add_test(NAME gitledger_cli_smoke COMMAND gitledger_tests)
endif()
