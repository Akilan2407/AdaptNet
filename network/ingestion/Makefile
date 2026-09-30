CC ?= clang
CFLAGS ?= -Wall -Wextra -O2 -I. -I../common -pthread
SRCS = data_ingestion.c record_parser.c data_validator.c data_store.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: $(OBJS)
	@echo "Compiled network/ingestion objects successfully."

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS)
	@echo "Cleaned network/ingestion build artifacts."
