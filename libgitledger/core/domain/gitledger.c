#include "gitledger/gitledger.h"

#define GITLEDGER_VERSION_MAJOR 0
#define GITLEDGER_VERSION_MINOR 1
#define GITLEDGER_VERSION_PATCH 0

int gitledger_version(void) {
    return (GITLEDGER_VERSION_MAJOR * 10000) +
           (GITLEDGER_VERSION_MINOR * 100) +
           (GITLEDGER_VERSION_PATCH);
}
