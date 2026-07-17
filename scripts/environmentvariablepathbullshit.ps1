# 1. Locate the Visual Studio installation base directory
$vsPath = "C:\Program Files\Microsoft Visual Studio\18\Community"
if (-not (Test-Path $vsPath)) {
    Write-Error "Visual Studio directory not found at $vsPath. Please check your version folder name."
    return
}

# 2. Brute force check the standard explicit location for CMake
$cmakeBinDir = "$vsPath\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin"
if (-not (Test-Path (Join-Path $cmakeBinDir "cmake.exe"))) {
    # Fallback search if path shifted slightly
    $cmakeBinDir = Resolve-Path "$vsPath\*\*\*\*\CMake\CMake\bin" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Path
}

# 3. Resolve the MSVC version folder using a basic wildcard (avoids deep recursive pipeline)
$msvcBase = "$vsPath\VC\Tools\MSVC"
$compilerBinDir = $null
if (Test-Path $msvcBase) {
    # Grabs the folder name (e.g., 14.40.33810) and builds the direct path
    $versionFolder = Get-ChildItem -Path $msvcBase -Directory | Select-Object -First 1 -ExpandProperty Name
    if ($versionFolder) {
        $compilerBinDir = "$msvcBase\$versionFolder\bin\Hostx64\x64"
    }
}

# 4. Verify paths exist on disk
if (-not $cmakeBinDir -or -not (Test-Path (Join-Path $cmakeBinDir "cmake.exe"))) {
    Write-Error "Failed to find cmake.exe at resolved path: $cmakeBinDir"
    return
}
if (-not $compilerBinDir -or -not (Test-Path (Join-Path $compilerBinDir "cl.exe"))) {
    Write-Error "Failed to find cl.exe at resolved path: $compilerBinDir"
    return
}

Write-Host "Found CMake at: $cmakeBinDir" -ForegroundColor Green
Write-Host "Found Compiler at: $compilerBinDir" -ForegroundColor Green

# 5. Fetch current User Path from Registry
$userEnvKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
$currentPath = $userEnvKey.GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)

# 6. Append paths
$pathUpdated = $false
foreach ($dir in @($cmakeBinDir, $compilerBinDir)) {
    if ($currentPath -notlike "*$dir*") {
        if ($currentPath -and -not $currentPath.EndsWith(";")) { $currentPath += ";" }
        $currentPath += $dir
        $pathUpdated = $true
    }
}

# 7. Commit changes and broadcast update
if ($pathUpdated) {
    $userEnvKey.SetValue("Path", $currentPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
    
    $signature = @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32Env {
        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
    }
"@
    # Avoid crashing if the type was already loaded in this session
    if (-not ([System.Management.Automation.PSTypeName]'Win32Env').Type) {
        Add-Type -TypeDefinition $signature
    }
    $result = [UIntPtr]::Zero
    [Win32Env]::SendMessageTimeout([IntPtr]0xffff, 0x001A, [UIntPtr]::Zero, "Environment", 2, 5000, [ref]$result)
    
    Write-Host "System environment variables permanently updated. Restart your terminal to apply changes." -ForegroundColor Cyan
} else {
    Write-Host "Paths are already configured in your environment variable setup." -ForegroundColor Yellow
}

$userEnvKey.Close()