project('libgitledger', 'c',
  version: '0.1.0',
  default_options: ['c_std=c17', 'warning_level=3', 'werror=true']
)

include_dir = include_directories('include')

libgitledger = static_library(
  'gitledger',
  ['src/version.c'],
  include_directories: include_dir,
)

tests = executable(
  'gitledger_tests',
  'tests/version_test.c',
  include_directories: include_dir,
  link_with: libgitledger,
)

test('version', tests)
