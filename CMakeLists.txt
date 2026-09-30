cmake_minimum_required(VERSION 3.16)
project(AdaptiveNetworkTrafficManagement C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_compile_options(-Wall -Wextra -O2 -pthread)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/network/common)

# C Agent Executable
add_executable(agent network/agent/main.c)
target_include_directories(agent PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/network/common)

# C Controller Executable
add_executable(controller network/controller/main.c)
target_include_directories(controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/network/common)
