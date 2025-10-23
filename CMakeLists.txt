cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 23)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(MSVC)
    add_compile_options(/W4 /WX)
else()
    add_compile_options(-Wall -Wextra -Werror -Wpedantic -Wshadow -Wconversion)
endif()

add_library(gitledger STATIC
    src/version.c
)

target_include_directories(gitledger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

include(CTest)
add_executable(gitledger_tests tests/version_test.c)
target_link_libraries(gitledger_tests PRIVATE gitledger)
add_test(NAME version COMMAND gitledger_tests)
