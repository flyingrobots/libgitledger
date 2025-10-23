#include <stdio.h>
#include "gitledger/gitledger.h"

int main(void) {
    int version = gitledger_version();
    printf("libgitledger version: %d\n", version);
    return 0;
}
