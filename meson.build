project('libgitledger', 'c',
  version: '0.1.0',
  default_options: ['c_std=c17', 'warning_level=3', 'werror=true']
)

lib_sources = [
  'libgitledger/core/context.c',
  'libgitledger/core/domain/gitledger.c',
  'libgitledger/core/domain/error.c',
  'src/version.c',
]

include_dir = include_directories('libgitledger/include', 'include')

libgitledger = static_library(
  'gitledger',
  lib_sources,
  include_directories: include_dir,
  c_args: ['-DGITLEDGER_BUILD'],
)

tests_version = executable(
  'gitledger_version_test',
  'tests/version_test.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

test('version', tests_version)

tests_smoke = executable(
  'gitledger_cli_smoke',
  'libgitledger/tests/main.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

test('cli_smoke', tests_smoke)

executable(
  'mg-ledger',
  'libgitledger/cli/mg-ledger.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

tests_error = executable(
  'gitledger_error_test',
  'tests/error_test.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

test('error', tests_error)
