#ifndef DATA_VALIDATOR_H
#define DATA_VALIDATOR_H

#include <stddef.h>
#include "record_parser.h"

/*
 * Validate a parsed NetworkRecord against network integrity rules.
 * Normalizes protocol to uppercase ("TCP" or "UDP").
 * Returns 1 if valid, 0 if invalid (with detailed reason populated in error_msg).
 */
int validate_network_record(NetworkRecord *record, char *error_msg, size_t error_len);

#endif /* DATA_VALIDATOR_H */
