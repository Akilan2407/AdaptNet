#ifndef CONTROL_CONFIG_H
#define CONTROL_CONFIG_H

#include <stddef.h>
#include <stdint.h>

/* Phase 14 Adaptive Traffic Control Configuration */

/* Priority Levels (Aligned with Phase 13) */
typedef enum {
    PRIO_LEVEL_LOW    = 0,
    PRIO_LEVEL_NORMAL = 1,
    PRIO_LEVEL_MEDIUM = 2,
    PRIO_LEVEL_HIGH   = 3,
    PRIO_LEVEL_UNKNOWN = -1
} priority_level_t;

/* Traffic Control Classes & Bandwidth Allocation */
#define HTB_ROOT_HANDLE_MAJOR 1
#define HTB_ROOT_CLASS_ID     "1:1"
#define HTB_CLASS_HIGH        "1:10"
#define HTB_CLASS_MEDIUM      "1:20"
#define HTB_CLASS_NORMAL      "1:30"
#define HTB_CLASS_LOW         "1:40"
#define HTB_DEFAULT_CLASS_NUM 30

/* Configurable Bandwidth & Ceiling Rates */
#define RATE_ROOT_TOTAL       "100mbit"
#define RATE_HIGH             "100mbit"
#define CEIL_HIGH             "100mbit"
#define TC_PRIO_HIGH          1

#define RATE_MEDIUM           "60mbit"
#define CEIL_MEDIUM           "80mbit"
#define TC_PRIO_MEDIUM        2

#define RATE_NORMAL           "30mbit"
#define CEIL_NORMAL           "50mbit"
#define TC_PRIO_NORMAL        3

#define RATE_LOW              "10mbit"
#define CEIL_LOW              "20mbit"
#define TC_PRIO_LOW           4

/* Default Mode: DRY_RUN = 1 (true) for safety */
#define DEFAULT_DRY_RUN 1

/* File Paths */
#define DEFAULT_QOS_DECISIONS_CSV "data/policy/qos_decisions.csv"
#define DEFAULT_CONTROL_ACTIONS_CSV "data/control/control_actions.csv"
#define DEFAULT_CONTROL_STATE_CSV   "data/control/control_state.csv"
#define DEFAULT_CONTROL_LOG_DIR     "data/control"

/* Allowlisted Network Interfaces (Mininet Topology) */
static const char *const ALLOWLISTED_INTERFACES[] = {
    "s1-eth1", "s1-eth2", "s1-eth3", "s1-eth4", "s1-eth5",
    "h1-eth0", "h2-eth0", "h3-eth0", "h4-eth0", "h5-eth0",
    "lo",
    NULL
};

/* Known Topology Devices */
static const char *const KNOWN_DEVICES[] = {
    "h1", "h2", "h3", "h4", "h5",
    NULL
};

/* Buffer Capacities */
#define MAX_CMD_LEN       1024
#define MAX_IP_LEN        64
#define MAX_DEVICE_LEN    32
#define MAX_IFACE_LEN     32
#define MAX_FLOW_ID_LEN   128
#define MAX_REASON_LEN    256
#define MAX_ERR_MSG_LEN   256
#define MAX_RULE_ID_LEN   64

#endif /* CONTROL_CONFIG_H */
