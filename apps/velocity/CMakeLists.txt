cmake_minimum_required(VERSION 3.15)
project(apex-velocity C CXX)

# Silence the FindBoost deprecation warning by opting into the new behavior
cmake_policy(SET CMP0167 NEW)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Core Dependencies
find_package(SDL2 CONFIG REQUIRED)
find_package(SFML COMPONENTS Graphics Window System Network Audio CONFIG REQUIRED)
find_package(Boost REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(pugixml CONFIG REQUIRED)
find_package(OpenSSL REQUIRED)

# Find PortAudio and JUCE
find_package(portaudio CONFIG REQUIRED)
find_package(JUCE CONFIG REQUIRED)

# Find Header-Only miniaudio (vcpkg does not use find_package for miniaudio)
find_path(MINIAUDIO_INCLUDE_DIRS "miniaudio.h" REQUIRED)

add_executable(${PROJECT_NAME} src/main.cpp)

# Fix: Prevent JUCE from blocking or rewriting your standard int main() entry point
target_compile_definitions(${PROJECT_NAME} PRIVATE 
    JUCE_ALLOW_STATIC_MAIN_FUNCTION=1
)

# Include both project headers and miniaudio path
target_include_directories(${PROJECT_NAME} PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${MINIAUDIO_INCLUDE_DIRS}
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    # Core Dependencies
    SDL2::SDL2
    SFML::Graphics
    SFML::Window
    SFML::System
    SFML::Network
    SFML::Audio
    Boost::boost
    nlohmann_json::nlohmann_json
    pugixml::pugixml
    OpenSSL::Crypto
    OpenSSL::SSL

    # Absolute Audio Control Engines
    portaudio

    # Core JUCE dependencies for bare-metal buffers and device routing
    juce::juce_core
    juce::juce_events
    juce::juce_audio_basics
    juce::juce_audio_devices
)