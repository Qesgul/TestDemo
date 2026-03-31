# PowerShell script to clean up temporary test files
$tempFiles = @(
    "check_*.py",
    "find_*.py",
    "try_*.py",
    "demo_*.html",
    "znzmo_*.html",
    "*.png"
)

foreach ($pattern in $tempFiles) {
    Get-ChildItem -Path . -Filter $pattern -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

Write-Host "Temporary files cleanup completed."
