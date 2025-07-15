# analyze_workspace.ps1

# Define output file
$outputFile = "error_report.txt"
"== Error Report Generated on $(Get-Date) ==" | Out-File $outputFile

# Step 1: Static analysis using pylint
"--- Running pylint ---" | Tee-Object -FilePath $outputFile -Append
pylint . --exit-zero | Tee-Object -FilePath $outputFile -Append

# Step 2: Type checking using mypy
"--- Running mypy ---" | Tee-Object -FilePath $outputFile -Append
mypy . --ignore-missing-imports | Tee-Object -FilePath $outputFile -Append

# Optional: Run API tests if you have them
if (Test-Path ".\tests") {
    "--- Running pytest ---" | Tee-Object -FilePath $outputFile -Append
    pytest --tb=short | Tee-Object -FilePath $outputFile -Append
}

# Completion message
Write-Host "✅ Analysis complete. See 'error_report.txt' for details." -ForegroundColor Green
