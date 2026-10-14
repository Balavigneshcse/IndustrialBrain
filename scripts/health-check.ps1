$Checks = @(
    @{ Name = "IndusMind API (readiness; the language model is optional)"; Url = "http://127.0.0.1:8000/api/v1/health/ready" },
    @{ Name = "React Frontend UI"; Url = "http://127.0.0.1:5173" }
)
$Failed = $false
foreach ($Check in $Checks) {
    try {
        $Response = Invoke-WebRequest -Uri $Check.Url -UseBasicParsing -TimeoutSec 5
        Write-Host "$($Check.Name): UP ($($Response.StatusCode))" -ForegroundColor Green
    } catch {
        Write-Host "$($Check.Name): DOWN" -ForegroundColor Red
        $Failed = $true
    }
}
if ($Failed) { exit 1 }
