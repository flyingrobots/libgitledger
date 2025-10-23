cmake_minimum_required(VERSION 3.20)
project(libgitledger VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/W4 /WX)
else()
    add_compile_options(-Wall -Wextra -Werror -fvisibility=hidden)
endif()

set(LIBGITLEDGER_SOURCES
    libgitledger/core/domain/gitledger.c
)

set(LIBGITLEDGER_HEADERS
    libgitledger/include/gitledger/gitledger.h
)

add_library(gitledger STATIC ${LIBGITLEDGER_SOURCES} ${LIBGITLEDGER_HEADERS})

target_include_directories(gitledger
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/libgitledger/include>
        $<INSTALL_INTERFACE:include>
)

add_executable(gitledger_tests libgitledger/tests/main.c)
target_link_libraries(gitledger_tests PRIVATE gitledger)

add_executable(mg-ledger libgitledger/cli/mg-ledger.c)
target_link_libraries(mg-ledger PRIVATE gitledger)

include(CTest)
if(BUILD_TESTING)
    add_test(NAME gitledger_tests COMMAND gitledger_tests)
endif()
