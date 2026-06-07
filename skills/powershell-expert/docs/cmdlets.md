# PowerShell Cmdlet Reference

## Pipeline Architecture

```powershell
# Object pipeline (not text)
Get-Process | Where-Object { $_.CPU -gt 100 } | Sort-Object CPU -Descending | Select-Object -First 5

# Filtering stages
Get-Service | Where-Object Status -eq 'Running'    # Fast (operator)
Get-Service | Where-Object { $_.Status -eq 'Running' }  # Script block (slower)

# Formatting
Get-Process | Format-Table Name, CPU, WorkingSet -AutoSize
Get-Process | Format-List *
Get-Process | Format-Wide Name

# Export
Get-Process | Export-Csv -Path .\processes.csv -NoTypeInformation
Get-Process | ConvertTo-Json | Set-Content .\processes.json
Get-Process | ConvertTo-Html | Set-Content .\processes.html
```

## Common Cmdlets

### File System
```powershell
Get-ChildItem -Path . -Recurse -Filter *.ps1
Copy-Item -Path .\file.txt -Destination .\backup\ -Force
Move-Item -Path .\old.txt -Destination .\new.txt
Remove-Item -Path .\temp -Recurse -Force
New-Item -Path .\newdir -ItemType Directory
Test-Path -Path .\file.txt
Get-Content -Path .\file.txt -Raw
Set-Content -Path .\file.txt -Value "Hello"
Add-Content -Path .\file.txt -Value "World"
```

### Services & Processes
```powershell
Get-Service -Name w3svc, spooler
Start-Service -Name w3svc
Stop-Service -Name w3svc -Force
Restart-Service -Name w3svc
Get-Process -Name notepad
Stop-Process -Name notepad -Force
Start-Process -FilePath notepad.exe -ArgumentList "file.txt"
```

### Networking
```powershell
Test-NetConnection -ComputerName google.com -Port 443
Invoke-WebRequest -Uri "https://api.example.com/data" -UseBasicParsing
Invoke-RestMethod -Uri "https://api.example.com/data"
Resolve-DnsName -Name google.com
Get-NetAdapter | Select-Object Name, Status, LinkSpeed
Test-Path -Path "\\server\share"
```

### Registry
```powershell
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion"
Set-ItemProperty -Path "HKCU:\Software\MyApp" -Name "Setting" -Value 1
New-ItemProperty -Path "HKLM:\SOFTWARE\MyApp" -Name "NewKey" -Value 1 -PropertyType DWORD
Remove-ItemProperty -Path "HKCU:\Software\MyApp" -Name "OldKey"
```

### Windows Features
```powershell
Get-WindowsFeature -Name Web-*
Install-WindowsFeature -Name Web-Server -IncludeManagementTools
Remove-WindowsFeature -Name Web-Server
Enable-WindowsOptionalFeature -Online -FeatureName NetFx3
```

## Parameter Validation

```powershell
function Test-Validation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Name,

        [Parameter()]
        [ValidateRange(1, 100)]
        [int]$Count = 10,

        [Parameter()]
        [ValidateSet('Low', 'Medium', 'High')]
        [string]$Priority = 'Medium',

        [Parameter()]
        [ValidatePattern('^[a-zA-Z0-9_-]+$')]
        [string]$Identifier,

        [Parameter()]
        [ValidateScript({ Test-Path $_ -PathType Leaf })]
        [string]$FilePath,

        [Parameter()]
        [ValidateCount(1, 5)]
        [string[]]$Tags,

        [Parameter()]
        [ValidateNotNull()]
        [hashtable]$Options
    )

    process {
        "Name: $Name, Count: $Count, Priority: $Priority"
    }
}
```

## Error Handling

```powershell
# Try/Catch/Finally
try {
    $result = Invoke-RestMethod -Uri "https://api.example.com" -ErrorAction Stop
}
catch [System.Net.WebException] {
    Write-Warning "Network error: $($_.Exception.Message)"
}
catch {
    Write-Error "Unexpected error: $_"
}
finally {
    # Cleanup code
    Disconnect-Path -Name "APIConnection" -ErrorAction SilentlyContinue
}

# Error action preferences
$ErrorActionPreference = 'Stop'    # All errors are terminating
$ErrorActionPreference = 'Continue' # Non-terminating errors continue
$ErrorActionPreference = 'SilentlyContinue' # Suppress errors
$ErrorActionPreference = 'Ignore'  # Suppress and remove from $Error

# Per-cmdlet error action
Get-Thing -ErrorAction SilentlyContinue
Get-Thing -ErrorAction Stop
```

## Splatting

```powershell
# Build parameters as hashtable
$params = @{
    Path        = "C:\Logs"
    Recurse     = $true
    Filter      = "*.log"
    ErrorAction = 'SilentlyContinue'
}

# splat with @
Get-ChildItem @params

# Automatic splatting with $PSBoundParameters
function Invoke-WithDefaults {
    [CmdletBinding()]
    param(
        [string]$Server,
        [int]$Timeout = 30,
        [switch]$Verbose
    )

    $defaults = @{ Timeout = 30; ErrorAction = 'Stop' }
    $allParams = $defaults + $PSBoundParameters

    Invoke-Command @allParams
}
```
