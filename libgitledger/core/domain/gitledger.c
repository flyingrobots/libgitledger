#include "gitledger/gitledger.h"

#define GITLEDGER_VERSION_MAJOR 0
#define GITLEDGER_VERSION_MINOR 1
#define GITLEDGER_VERSION_PATCH 0

/* Encoded as major * 10000 + minor * 100 + patch for numeric comparisons (see version spec). */
enum
{
    GITLEDGER_VERSION_MAJOR_FACTOR = 10000,
    GITLEDGER_VERSION_MINOR_FACTOR = 100
};

int gitledger_version(void)
{
    return (GITLEDGER_VERSION_MAJOR * GITLEDGER_VERSION_MAJOR_FACTOR) +
           (GITLEDGER_VERSION_MINOR * GITLEDGER_VERSION_MINOR_FACTOR) + GITLEDGER_VERSION_PATCH;
}
