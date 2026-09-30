CC ?= clang
CFLAGS ?= -Wall -Wextra -O2 -I. -I../common -pthread
TARGET = monitor_agent
SRCS = monitor_agent.c flow_monitor.c network_stats.c socket_client.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)
	@echo "Built: network/agent/$(TARGET)"

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)
	@echo "Cleaned network/agent build artifacts."
