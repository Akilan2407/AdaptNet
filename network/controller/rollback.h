#ifndef ROLLBACK_H
#define ROLLBACK_H

#include <stdbool.h>
#include <stddef.h>
#include "control_config.h"

#define MAX_MANAGED_INTERFACES 16

/* Track managed interfaces */
bool register_managed_interface(const char *interface);
bool unregister_managed_interface(const char *interface);
size_t get_managed_interfaces(char out_interfaces[MAX_MANAGED_INTERFACES][MAX_IFACE_LEN]);

/* Rollback operations */
bool rollback_interface(const char *interface, bool dry_run, char *err_msg, size_t err_len);
int rollback_all(bool dry_run, char *err_msg, size_t err_len);

#endif /* ROLLBACK_H */
