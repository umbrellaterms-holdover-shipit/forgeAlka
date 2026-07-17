# Configure CMake using your existing global vcpkg toolchain
#cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE="$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake" -DVCPKG_TARGET_TRIPLET=x64-windows

# Compile the target binaries
cmake --build build --config Release