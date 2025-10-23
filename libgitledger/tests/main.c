#include "gitledger/gitledger.h"
#include <stdio.h>

int main(void)
{
    int version = gitledger_version();
    if (printf("libgitledger version: %d\n", version) < 0)
        {
            return 1;
        }
    return 0;
}
