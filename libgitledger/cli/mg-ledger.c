#include <stdio.h>
#include "gitledger/gitledger.h"

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    printf("mg-ledger (libgitledger %d) placeholder CLI\n", gitledger_version());
    return 0;
}
