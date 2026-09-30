CC ?= clang
CFLAGS ?= -Wall -Wextra -O2 -I./network/common -I./network/agent -I./network/controller -I./network/ingestion -pthread
BUILD_DIR = build
BIN_DIR = bin

AGENT_SRC = network/agent/main.c
CONTROLLER_SRC = network/controller/main.c
MONITOR_AGENT_SRCS = network/agent/monitor_agent.c network/agent/flow_monitor.c network/agent/network_stats.c network/agent/socket_client.c
INGESTION_SRCS = network/ingestion/data_ingestion.c network/ingestion/record_parser.c network/ingestion/data_validator.c network/ingestion/data_store.c
NETWORK_CONTROLLER_SRCS = network/controller/network_controller.c network/controller/client_handler.c $(INGESTION_SRCS)

AGENT_BIN = $(BIN_DIR)/agent
CONTROLLER_BIN = $(BIN_DIR)/controller
MONITOR_AGENT_BIN = $(BIN_DIR)/monitor_agent
NETWORK_CONTROLLER_BIN = $(BIN_DIR)/network_controller

.PHONY: all clean directories agent controller monitor_agent network_controller test

all: directories agent controller monitor_agent network_controller

directories:
	@mkdir -p $(BUILD_DIR) $(BIN_DIR)

agent: directories $(AGENT_SRC) network/common/protocol.h
	$(CC) $(CFLAGS) $(AGENT_SRC) -o $(AGENT_BIN)
	@echo "Built: $(AGENT_BIN)"

controller: directories $(CONTROLLER_SRC) network/common/protocol.h
	$(CC) $(CFLAGS) $(CONTROLLER_SRC) -o $(CONTROLLER_BIN)
	@echo "Built: $(CONTROLLER_BIN)"

monitor_agent: directories $(MONITOR_AGENT_SRCS)
	$(CC) $(CFLAGS) $(MONITOR_AGENT_SRCS) -o $(MONITOR_AGENT_BIN)
	@echo "Built: $(MONITOR_AGENT_BIN)"

network_controller: directories $(NETWORK_CONTROLLER_SRCS)
	$(CC) $(CFLAGS) $(NETWORK_CONTROLLER_SRCS) -o $(NETWORK_CONTROLLER_BIN)
	@echo "Built: $(NETWORK_CONTROLLER_BIN)"

test: all
	@echo "Running C Binaries Smoke Tests..."
	@$(AGENT_BIN) -v
	@$(CONTROLLER_BIN) -v
	@$(MONITOR_AGENT_BIN) --help > /dev/null
	@$(NETWORK_CONTROLLER_BIN) --help > /dev/null
	@echo "C build & smoke tests passed successfully!"

clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)
	@$(MAKE) -C network/agent clean
	@$(MAKE) -C network/controller clean
	@$(MAKE) -C network/ingestion clean
	@echo "Cleaned all build artifacts."
