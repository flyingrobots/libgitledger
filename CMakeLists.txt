cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

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
  if(NOT MSVC)
    target_link_options(${target} PRIVATE -nostdlib)
  endif()
endfunction()

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
endif()
add_nostdlib(gitledger)
add_nostdlib(gitledger_version_test)
add_nostdlib(gitledger_tests)
add_nostdlib(mg-ledger)
add_nostdlib(gitledger_error_test)
