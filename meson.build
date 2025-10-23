project('libgitledger', 'c',
  version: '0.1.0',
  default_options: ['c_std=c11', 'warning_level=3', 'werror=true']
)

lib_sources = [
  'libgitledger/core/domain/gitledger.c',
]

include_dir = include_directories('libgitledger/include')

libgitledger = static_library(
  'gitledger',
  lib_sources,
  include_directories: include_dir,
)

tests_exe = executable(
  'gitledger_tests',
  'libgitledger/tests/main.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

test('gitledger_tests', tests_exe)

executable(
  'mg-ledger',
  'libgitledger/cli/mg-ledger.c',
  include_directories: include_dir,
  link_with: libgitledger,
)
