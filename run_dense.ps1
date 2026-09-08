# Run the local dense service using the project's Python environment.
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot/.venv/Scripts/python.exe" -m services.dense_service
    $serviceExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $serviceExitCode
