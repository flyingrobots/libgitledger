cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(MSVC)
    set(PROJECT_WARNING_FLAGS /W4 /WX)
else()
    # Keep Unix builds strict: treat warnings as errors and enable extra diagnostics.
    set(PROJECT_WARNING_FLAGS -Wall -Wextra -Werror -Wpedantic -Wshadow -Wconversion)
endif()

add_library(gitledger STATIC
    src/version.c
)

target_compile_options(gitledger PRIVATE ${PROJECT_WARNING_FLAGS})
target_include_directories(gitledger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

include(CTest)
add_executable(gitledger_tests tests/version_test.c)
target_compile_options(gitledger_tests PRIVATE ${PROJECT_WARNING_FLAGS})
target_link_libraries(gitledger_tests PRIVATE gitledger)
add_test(NAME version COMMAND gitledger_tests)
