#include "gitledger/gitledger.h"
#include <stdio.h>

int main(int argc, char** argv)
{
    (void) argc;
    (void) argv;
    const int version = gitledger_version();
    if (printf("mg-ledger (libgitledger %d) placeholder CLI\n", version) < 0)
        {
            return 1;
        }
    return 0;
}
