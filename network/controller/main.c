#include <stdio.h>
#include <stdlib.h>
#include "protocol.h"

int main(int argc, char *argv[]) {
    printf("=====================================================\n");
    printf("Adaptive Network Traffic Management - C Network Controller\n");
    printf("Version: 0.1.0 (Phase 1 Skeleton)\n");
    printf("Default Controller Port: %d | Agent Port: %d\n", DEFAULT_CONTROLLER_PORT, DEFAULT_AGENT_PORT);
    printf("=====================================================\n");

    if (argc > 1 && (argv[1][0] == '-' && argv[1][1] == 'v')) {
        return 0;
    }

    printf("Network Controller initialized in standby mode.\n");
    return 0;
}
