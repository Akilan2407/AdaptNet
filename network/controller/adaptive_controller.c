#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "control_config.h"
#include "control_interface.h"
#include "flow_mapper.h"
#include "control_logger.h"
#include "rollback.h"

static void print_usage(const char *prog_name) {
    printf("Usage: %s [OPTIONS]\n\n", prog_name);
    printf("Phase 14 Adaptive Traffic Controller (Linux / Mininet)\n\n");
    printf("Options:\n");
    printf("  --apply-csv <file>   Load Phase 13 QoS decisions CSV and apply controls\n");
    printf("                       (default: %s)\n", DEFAULT_QOS_DECISIONS_CSV);
    printf("  --dry-run            Simulate control actions without modifying kernel (DEFAULT)\n");
    printf("  --enforce            Execute actual tc commands (Linux/Mininet only)\n");
    printf("  --rollback           Reset and remove all project-applied tc rules\n");
    printf("  --status             Display active controller rules\n");
    printf("  --help, -h           Show this help message\n");
}

static int parse_csv_line(char *line, char *fields[], int max_fields) {
    int count = 0;
    char *cursor = line;
    while (cursor && count < max_fields) {
        char *comma = strchr(cursor, ',');
        if (comma) {
            *comma = '\0';
            fields[count++] = cursor;
            cursor = comma + 1;
        } else {
            char *eol = strpbrk(cursor, "\r\n");
            if (eol) *eol = '\0';
            fields[count++] = cursor;
            break;
        }
    }
    return count;
}

int main(int argc, char *argv[]) {
    const char *csv_path = NULL;
    bool dry_run = DEFAULT_DRY_RUN;
    bool do_rollback = false;
    bool do_status = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--apply-csv") == 0 && i + 1 < argc) {
            csv_path = argv[++i];
        } else if (strcmp(argv[i], "--dry-run") == 0) {
            dry_run = true;
        } else if (strcmp(argv[i], "--enforce") == 0) {
            dry_run = false;
        } else if (strcmp(argv[i], "--rollback") == 0) {
            do_rollback = true;
        } else if (strcmp(argv[i], "--status") == 0) {
            do_status = true;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    init_control_subsystem(dry_run);

    if (do_rollback) {
        printf("[*] Executing Rollback on all managed interfaces (dry_run=%s)...\n", dry_run ? "true" : "false");
        control_request_t req = {0};
        req.command = CMD_RESET;
        req.dry_run = dry_run;
        control_response_t resp = {0};
        dispatch_control_request(&req, &resp);
        printf("[+] Rollback completed. Status: %s (%s)\n", resp.status_str, resp.executed_command);
        shutdown_control_subsystem();
        return 0;
    }

    if (do_status) {
        control_request_t req = {0};
        req.command = CMD_STATUS;
        control_response_t resp = {0};
        dispatch_control_request(&req, &resp);
        printf("[*] Controller Status: %s (%s)\n", resp.status_str, resp.executed_command);
        shutdown_control_subsystem();
        return 0;
    }

    if (!csv_path) {
        csv_path = DEFAULT_QOS_DECISIONS_CSV;
    }

    FILE *f = fopen(csv_path, "r");
    if (!f) {
        fprintf(stderr, "[-] Error: Failed to open decisions CSV at '%s'\n", csv_path);
        shutdown_control_subsystem();
        return 1;
    }

    printf("========================================\n");
    printf("PHASE 14 — ADAPTIVE TRAFFIC CONTROLLER\n");
    printf("========================================\n");
    printf("Mode: %s\n", dry_run ? "DRY-RUN (Safe Simulation)" : "ENFORCE (Active Kernel Actuation)");
    printf("Input Decisions: %s\n\n", csv_path);

    char line[2048];
    // Read header line
    if (!fgets(line, sizeof(line), f)) {
        fprintf(stderr, "[-] Error: Empty CSV file\n");
        fclose(f);
        shutdown_control_subsystem();
        return 1;
    }

    // Determine column indices
    int col_ts = -1, col_dev = -1, col_flow = -1, col_tc = -1, col_cong = -1, col_prio = -1, col_comp = -1;
    char *hdr_fields[64] = {0};
    int num_hdr = parse_csv_line(line, hdr_fields, 64);
    for (int i = 0; i < num_hdr; i++) {
        if (strcmp(hdr_fields[i], "timestamp") == 0) col_ts = i;
        else if (strcmp(hdr_fields[i], "device_id") == 0) col_dev = i;
        else if (strcmp(hdr_fields[i], "flow_id") == 0) col_flow = i;
        else if (strcmp(hdr_fields[i], "traffic_class") == 0) col_tc = i;
        else if (strcmp(hdr_fields[i], "predicted_congestion_class") == 0) col_cong = i;
        else if (strcmp(hdr_fields[i], "final_priority") == 0) col_prio = i;
        else if (strcmp(hdr_fields[i], "input_completeness") == 0) col_comp = i;
    }

    int total_processed = 0;
    int total_applied = 0;
    int total_updated = 0;
    int total_skipped = 0;
    int total_failed = 0;

    while (fgets(line, sizeof(line), f)) {
        char *fields[64] = {0};
        int f_count = parse_csv_line(line, fields, 64);

        if (f_count <= col_prio) {
            continue;
        }

        total_processed++;
        const char *ts = (col_ts >= 0 && col_ts < f_count) ? fields[col_ts] : "";
        const char *device_id = (col_dev >= 0 && col_dev < f_count) ? fields[col_dev] : "";
        const char *flow_id = (col_flow >= 0 && col_flow < f_count) ? fields[col_flow] : "";
        const char *traffic_class = (col_tc >= 0 && col_tc < f_count) ? fields[col_tc] : "OTHER";
        const char *cong_class = (col_cong >= 0 && col_cong < f_count) ? fields[col_cong] : "UNKNOWN";
        const char *priority_str = (col_prio >= 0 && col_prio < f_count) ? fields[col_prio] : "NORMAL";
        const char *completeness = (col_comp >= 0 && col_comp < f_count) ? fields[col_comp] : "COMPLETE";

        // Section 19 Fallback Behavior: If input is PARTIAL, skip restriction and log as SKIPPED
        if (strcmp(completeness, "COMPLETE") != 0) {
            control_log_entry_t skip_log = {0};
            strncpy(skip_log.timestamp, ts, sizeof(skip_log.timestamp) - 1);
            strncpy(skip_log.device_id, device_id, sizeof(skip_log.device_id) - 1);
            strncpy(skip_log.flow_id, flow_id, sizeof(skip_log.flow_id) - 1);
            strncpy(skip_log.traffic_class, traffic_class, sizeof(skip_log.traffic_class) - 1);
            strncpy(skip_log.predicted_congestion_class, cong_class, sizeof(skip_log.predicted_congestion_class) - 1);
            strncpy(skip_log.final_priority, priority_str, sizeof(skip_log.final_priority) - 1);
            strncpy(skip_log.action, "APPLY", sizeof(skip_log.action) - 1);
            strncpy(skip_log.status, "SKIPPED", sizeof(skip_log.status) - 1);
            skip_log.dry_run = dry_run;
            snprintf(skip_log.error_message, sizeof(skip_log.error_message), "Input completeness PARTIAL; default handling retained");
            log_control_action(&skip_log);

            total_skipped++;
            continue;
        }

        // Parse 5-tuple
        flow_tuple_t tuple;
        if (!parse_flow_id(flow_id, &tuple)) {
            total_failed++;
            continue;
        }

        control_request_t req = {0};
        req.command = CMD_APPLY;
        strncpy(req.device_id, tuple.device_id, sizeof(req.device_id) - 1);
        strncpy(req.flow_id, flow_id, sizeof(req.flow_id) - 1);
        strncpy(req.src_ip, tuple.src_ip, sizeof(req.src_ip) - 1);
        strncpy(req.dst_ip, tuple.dst_ip, sizeof(req.dst_ip) - 1);
        req.src_port = tuple.src_port;
        req.dst_port = tuple.dst_port;
        strncpy(req.protocol, tuple.protocol, sizeof(req.protocol) - 1);
        strncpy(req.traffic_class, traffic_class, sizeof(req.traffic_class) - 1);
        strncpy(req.predicted_congestion_class, cong_class, sizeof(req.predicted_congestion_class) - 1);
        req.priority = parse_priority_string(priority_str);
        strncpy(req.interface, tuple.interface, sizeof(req.interface) - 1);
        req.dry_run = dry_run;

        control_response_t resp = {0};
        dispatch_control_request(&req, &resp);

        if (resp.status == CTRL_STATUS_SUCCESS || resp.status == CTRL_STATUS_DRY_RUN) {
            total_applied++;
        } else if (resp.status == CTRL_STATUS_SKIPPED) {
            total_skipped++;
        } else {
            total_failed++;
        }
    }
    fclose(f);

    printf("Control Processing Summary:\n");
    printf("  Total Decisions Evaluated : %d\n", total_processed);
    printf("  Rules Applied / Simulated : %d\n", total_applied);
    printf("  Rules Updated             : %d\n", total_updated);
    printf("  Rules Skipped (Fallback)  : %d\n", total_skipped);
    printf("  Operations Failed         : %d\n", total_failed);
    printf("\nOutputs:\n");
    printf("  Actions Log : %s\n", DEFAULT_CONTROL_ACTIONS_CSV);
    printf("  State Log   : %s\n", DEFAULT_CONTROL_STATE_CSV);
    printf("========================================\n");

    shutdown_control_subsystem();
    return (total_failed == 0) ? 0 : 1;
}
