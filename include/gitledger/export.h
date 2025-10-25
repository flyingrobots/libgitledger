#ifndef GITLEDGER_EXPORT_H
#define GITLEDGER_EXPORT_H

#if defined(_WIN32) || defined(__CYGWIN__)
#  ifdef GITLEDGER_BUILD
#    define GITLEDGER_API __declspec(dllexport)
#  else
#    define GITLEDGER_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__)
#  define GITLEDGER_API __attribute__((visibility("default")))
#else
#  define GITLEDGER_API
#endif

#endif /* GITLEDGER_EXPORT_H */
