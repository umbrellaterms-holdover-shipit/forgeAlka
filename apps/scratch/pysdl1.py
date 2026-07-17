import sys
import ctypes
import math
import os
import sdl2

# Try to import sdlttf for font rendering, fall back cleanly if missing
try:
    import sdl2.sdlttf
    HAS_TTF = True
except ImportError:
    HAS_TTF = False

WIDTH, HEIGHT = 800, 600

# Sieve setup
LIMIT = 120
states = [0] * (LIMIT + 1)
states[0] = states[1] = 2

p = 2
m = p * p
sieve_complete = False
last_eliminated = None

# Colors (RGBA)
COLOR_BG = (15, 15, 20, 255)
COLOR_UNCHECKED = (200, 200, 200, 255)
COLOR_PRIME = (50, 205, 50, 255)
COLOR_COMPOSITE = (70, 70, 80, 255)
COLOR_CURRENT_P = (0, 191, 255, 255)
COLOR_CURRENT_M = (255, 69, 0, 255)
COLOR_LINE = (40, 40, 50, 255)

def find_system_font():
    """Locate a common system TTF font."""
    paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None

def draw_filled_circle(renderer, cx, cy, r, color):
    """Draws a filled circle using raw horizontal scanlines."""
    sdl2.SDL_SetRenderDrawColor(renderer, color[0], color[1], color[2], color[3])
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        sdl2.SDL_RenderDrawLine(renderer, cx - dx, cy + dy, cx + dx, cy + dy)

def main():
    global p, m, sieve_complete, last_eliminated

    # Initialize SDL2 Video Subsystem
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) < 0:
        print(f"SDL could not initialize! SDL_Error: {sdl2.SDL_GetError()}")
        return

    window = sdl2.SDL_CreateWindow(
        b"Sieve of Eratosthenes & Sine Wave (PySDL2)",
        sdl2.SDL_WINDOWPOS_CENTERED,
        sdl2.SDL_WINDOWPOS_CENTERED,
        WIDTH, HEIGHT,
        sdl2.SDL_WINDOW_SHOWN
    )
    if not window:
        print(f"Window could not be created! SDL_Error: {sdl2.SDL_GetError()}")
        sdl2.SDL_Quit()
        return

    renderer = sdl2.SDL_CreateRenderer(
        window, -1, sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
    )
    if not renderer:
        print(f"Renderer could not be created! SDL_Error: {sdl2.SDL_GetError()}")
        sdl2.SDL_DestroyWindow(window)
        sdl2.SDL_Quit()
        return

    # Attempt to initialize fonts via SDL_ttf
    font = None
    ttf_initialized = False
    if HAS_TTF and sdl2.sdlttf.TTF_Init() == 0:
        font_path = find_system_font()
        if font_path:
            font = sdl2.sdlttf.TTF_OpenFont(font_path.encode('utf-8'), 12)
            if font:
                ttf_initialized = True
    
    if not ttf_initialized:
        print("Warning: TTF system not loaded or font file not found. Rendering nodes without text labels.")

    event = sdl2.SDL_Event()
    running = True
    phase = 0.0
    frame_count = 0
    STEP_DELAY = 10

    while running:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                running = False

        # Update Sieve State
        if not sieve_complete:
            frame_count += 1
            if frame_count >= STEP_DELAY:
                frame_count = 0
                
                if p * p <= LIMIT:
                    if m <= LIMIT:
                        states[m] = 2
                        last_eliminated = m
                        m += p
                    else:
                        states[p] = 1
                        last_eliminated = None
                        next_p = p + 1
                        while next_p <= LIMIT and states[next_p] == 2:
                            next_p += 1
                        if next_p * next_p <= LIMIT:
                            p = next_p
                            m = p * p
                        else:
                            for i in range(2, LIMIT + 1):
                                if states[i] == 0:
                                    states[i] = 1
                            sieve_complete = True
                            last_eliminated = None
                else:
                    sieve_complete = True
                    last_eliminated = None

        phase += 0.05

        # Clear background
        sdl2.SDL_SetRenderDrawColor(renderer, COLOR_BG[0], COLOR_BG[1], COLOR_BG[2], COLOR_BG[3])
        sdl2.SDL_RenderClear(renderer)

        # 1. Draw continuous background sine wave line
        sdl2.SDL_SetRenderDrawColor(renderer, COLOR_LINE[0], COLOR_LINE[1], COLOR_LINE[2], COLOR_LINE[3])
        prev_x, prev_y = None, None
        for screen_x in range(50, WIDTH - 50, 4):
            i_val = 2 + (screen_x - 50) / (WIDTH - 100) * (LIMIT - 2)
            y = HEIGHT // 2 + 100 * math.sin(0.1 * i_val + phase)
            if prev_x is not None:
                sdl2.SDL_RenderDrawLine(renderer, int(prev_x), int(prev_y), int(screen_x), int(y))
            prev_x, prev_y = screen_x, y

        # 2. Draw sieve nodes
        for i in range(2, LIMIT + 1):
            x = 50 + (i - 2) * (WIDTH - 100) / (LIMIT - 2)
            y = HEIGHT // 2 + 100 * math.sin(0.1 * i + phase)

            if i == p and not sieve_complete:
                color = COLOR_CURRENT_P
                radius = 12
            elif i == last_eliminated and not sieve_complete:
                color = COLOR_CURRENT_M
                radius = 10
            elif states[i] == 1:
                color = COLOR_PRIME
                radius = 8
            elif states[i] == 2:
                color = COLOR_COMPOSITE
                radius = 6
            else:
                color = COLOR_UNCHECKED
                radius = 8

            draw_filled_circle(renderer, int(x), int(y), radius, color)

            # Draw text label if TTF is ready
            if ttf_initialized:
                text_color = sdl2.SDL_Color(255, 255, 255, 255)
                text_surface = sdl2.sdlttf.TTF_RenderText_Blended(font, str(i).encode('utf-8'), text_color)
                if text_surface:
                    texture = sdl2.SDL_CreateTextureFromSurface(renderer, text_surface)
                    if texture:
                        w = text_surface.contents.w
                        h = text_surface.contents.h
                        dst_rect = sdl2.SDL_Rect(int(x) - w // 2, int(y) - radius - 15, w, h)
                        sdl2.SDL_RenderCopy(renderer, texture, None, dst_rect)
                        sdl2.SDL_DestroyTexture(texture)
                    sdl2.SDL_FreeSurface(text_surface)

        sdl2.SDL_RenderPresent(renderer)
        sdl2.SDL_Delay(16)  # Maintain ~60 FPS capping

    # Cleanup
    if ttf_initialized and font:
        sdl2.sdlttf.TTF_CloseFont(font)
    if ttf_initialized:
        sdl2.sdlttf.TTF_Quit()
    sdl2.SDL_DestroyRenderer(renderer)
    sdl2.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()

if __name__ == "__main__":
    main()