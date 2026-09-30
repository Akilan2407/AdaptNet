UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
    CC ?= /Library/Developer/CommandLineTools/usr/bin/clang
    SYSROOT_FLAG := $(shell if [ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk" ]; then echo "-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"; fi)
    CFLAGS ?= -Wall -Wextra -O2 -I. -I../common -I../ingestion -pthread $(SYSROOT_FLAG)
else
    CC ?= clang
    CFLAGS ?= -Wall -Wextra -O2 -I. -I../common -I../ingestion -pthread
endif

TARGETS = network_controller adaptive_controller

# Network Controller sources
NET_SRCS = network_controller.c client_handler.c \
           ../ingestion/data_ingestion.c ../ingestion/record_parser.c \
           ../ingestion/data_validator.c ../ingestion/data_store.c

# Adaptive Traffic Controller sources (Phase 14)
ADAPTIVE_SRCS = adaptive_controller.c control_interface.c flow_mapper.c \
                tc_manager.c control_logger.c rollback.c

.PHONY: all clean

all: $(TARGETS)

network_controller: $(NET_SRCS)
	$(CC) $(CFLAGS) $(NET_SRCS) -o network_controller
	@echo "Built: network/controller/network_controller"

adaptive_controller: $(ADAPTIVE_SRCS)
	$(CC) $(CFLAGS) $(ADAPTIVE_SRCS) -o adaptive_controller
	@echo "Built: network/controller/adaptive_controller"

clean:
	rm -f $(TARGETS) *.o
	@echo "Cleaned network/controller build artifacts."
