# CMake generated Testfile for 
# Source directory: /Users/james/git/libgitledger
# Build directory: /Users/james/git/libgitledger/build-asan
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test([=[version]=] "/Users/james/git/libgitledger/build-asan/gitledger_version_test")
set_tests_properties([=[version]=] PROPERTIES  _BACKTRACE_TRIPLES "/Users/james/git/libgitledger/CMakeLists.txt;60;add_test;/Users/james/git/libgitledger/CMakeLists.txt;0;")
add_test([=[gitledger_cli_smoke]=] "/Users/james/git/libgitledger/build-asan/gitledger_tests")
set_tests_properties([=[gitledger_cli_smoke]=] PROPERTIES  _BACKTRACE_TRIPLES "/Users/james/git/libgitledger/CMakeLists.txt;61;add_test;/Users/james/git/libgitledger/CMakeLists.txt;0;")
add_test([=[error]=] "/Users/james/git/libgitledger/build-asan/gitledger_error_test")
set_tests_properties([=[error]=] PROPERTIES  _BACKTRACE_TRIPLES "/Users/james/git/libgitledger/CMakeLists.txt;62;add_test;/Users/james/git/libgitledger/CMakeLists.txt;0;")
