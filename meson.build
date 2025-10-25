project('libgitledger', 'c',
  version: '0.1.0',
  default_options: ['c_std=c99', 'warning_level=3', 'werror=true']
)

vendor_libgit2 = get_option('vendor_libgit2')
with_libgit2_opt = get_option('with_libgit2')

if vendor_libgit2
  error('Vendored libgit2 support is not yet implemented. Install libgit2 or configure with -Dvendor_libgit2=false.')
endif

libgit2_required = with_libgit2_opt.enabled()
libgit2_dep = dependency('libgit2', required: libgit2_required)

if not libgit2_dep.found()
  if with_libgit2_opt.disabled()
    message('libgit2 disabled by configuration; continuing without it.')
  else
    message('libgit2 development files not found; install via your package manager (e.g. apt install libgit2-dev, brew install libgit2, or choco install libgit2).')
    if libgit2_required
      error('libgit2 was requested but could not be located.')
    endif
  endif
endif

if not get_option('with_croaring').disabled()
  message('CRoaring support is not implemented yet; option is currently informational only.')
endif

if not get_option('with_blake3').disabled()
  message('BLAKE3 support is not implemented yet; option is currently informational only.')
endif

lib_sources = [
  'libgitledger/core/context.c',
  'libgitledger/core/domain/gitledger.c',
  'libgitledger/core/domain/error.c',
  'src/version.c',
]

include_dir = include_directories('libgitledger/include', 'include')

cc = meson.get_compiler('c')
warn_flags = ['-Wall','-Wextra','-Werror','-pedantic','-std=c99']
if cc.has_argument('-Wno-fun')
  warn_flags += ['-Wno-fun']
endif


lib_deps = []
lib_c_args = []
if libgit2_dep.found()
  lib_deps += libgit2_dep
  lib_c_args += ['-DGITLEDGER_HAVE_LIBGIT2=1']
endif

libgitledger = static_library(
  'gitledger',
  lib_sources,
  include_directories: include_dir,
  dependencies: lib_deps,
  c_args: lib_c_args + ['-DGITLEDGER_BUILD'] + warn_flags,
  )

tests_version = executable(
  'gitledger_version_test',
  'tests/version_test.c',
  include_directories: include_dir,
  link_with: libgitledger,
  c_args: warn_flags,
  )

test('version', tests_version)

tests_smoke = executable(
  'gitledger_cli_smoke',
  'libgitledger/tests/main.c',
  include_directories: include_dir,
  link_with: libgitledger,
  c_args: warn_flags,
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
  c_args: warn_flags,
  )

test('error', tests_error)
