cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(MSVC)
    set(PROJECT_WARNING_FLAGS /W4 /WX /we4244 /we4267 /we4456 /we4457 /we4458 /we4459)
else()
    # Keep Unix builds strict and hide unintended symbol exports.
    set(PROJECT_WARNING_FLAGS -Wall -Wextra -Werror -Wpedantic -Wshadow -Wconversion -fvisibility=hidden)
endif()

set(LIBGITLEDGER_SOURCES
    libgitledger/core/context.c
    libgitledger/core/domain/gitledger.c
    libgitledger/core/domain/error.c
    src/version.c
)

set(LIBGITLEDGER_HEADERS
    libgitledger/include/gitledger/gitledger.h
    include/libgitledger/version.h
)

add_library(gitledger STATIC ${LIBGITLEDGER_SOURCES} ${LIBGITLEDGER_HEADERS})
target_compile_options(gitledger PRIVATE ${PROJECT_WARNING_FLAGS})

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
