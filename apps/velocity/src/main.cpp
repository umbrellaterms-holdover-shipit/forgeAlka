#include <iostream>
#include <SDL2/SDL.h>
#include <SFML/Graphics.hpp>
#include <nlohmann/json.hpp>
#include <openssl/sha.h>

using json = nlohmann::json;

int main() {
    json j = {{"status", "offline-ready"}, {"engine", "apex"}};
    std::cout << j.dump(4) << std::endl;

    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        std::cerr << "SDL init failed: " << SDL_GetError() << std::endl;
        return 1;
    }
    std::cout << "SDL Initialized successfully." << std::endl;
    SDL_Quit();

    return 0;
}
