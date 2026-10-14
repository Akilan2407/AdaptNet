PYTHON ?= python3
BUILD_DIR = build
BIN_DIR = bin

AGENT_BIN = $(BIN_DIR)/agent
CONTROLLER_BIN = $(BIN_DIR)/controller
MONITOR_AGENT_BIN = $(BIN_DIR)/monitor_agent
NETWORK_CONTROLLER_BIN = $(BIN_DIR)/network_controller
ADAPTIVE_CONTROLLER_BIN = network/controller/adaptive_controller

.PHONY: all clean directories agent controller monitor_agent network_controller adaptive_controller test

all: directories agent controller monitor_agent network_controller adaptive_controller

directories:
	@mkdir -p $(BUILD_DIR) $(BIN_DIR)

agent: directories network/agent/main.py
	@chmod +x $(AGENT_BIN)
	@echo "Ready: $(AGENT_BIN)"

controller: directories network/controller/main.py
	@chmod +x $(CONTROLLER_BIN)
	@echo "Ready: $(CONTROLLER_BIN)"

monitor_agent: directories network/agent/monitor_agent.py
	@chmod +x $(MONITOR_AGENT_BIN) network/agent/monitor_agent
	@echo "Ready: $(MONITOR_AGENT_BIN)"

network_controller: directories network/controller/network_controller.py
	@chmod +x $(NETWORK_CONTROLLER_BIN) network/controller/network_controller
	@echo "Ready: $(NETWORK_CONTROLLER_BIN)"

adaptive_controller: directories network/controller/adaptive_controller.py
	@chmod +x $(ADAPTIVE_CONTROLLER_BIN)
	@echo "Ready: $(ADAPTIVE_CONTROLLER_BIN)"

test: all
	@echo "Running Python Network Tests..."
	@$(AGENT_BIN) -v
	@$(CONTROLLER_BIN) -v
	@$(MONITOR_AGENT_BIN) --help > /dev/null
	@$(NETWORK_CONTROLLER_BIN) --help > /dev/null
	@echo "Python smoke tests passed successfully!"

clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned all build artifacts."
