# PowerShell Setup & Environment

## Installation

### Windows (built-in)
- Windows 10/11: PowerShell 5.1 pre-installed
- Open as Administrator for full access

### PowerShell 7+ (recommended)
```powershell
# Via winget (recommended)
winget install Microsoft.PowerShell

# Via MSI installer
# Download from https://github.com/PowerShell/PowerShell/releases

# Via Chocolatey
choco install powershell

# Via Scoop
scoop install powershell
```

## Execution Policy
```powershell
# Check current policy
Get-ExecutionPolicy -List

# Set policy for current user (recommended)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Bypass for single script
powershell -ExecutionPolicy Bypass -File .\script.ps1

# Set via registry (admin)
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell' -Name ExecutionPolicy -Value RemoteSigned
```

## PowerShell Profile
```powershell
# Profile paths
$PROFILE.CurrentUserAllHosts    # All users, all hosts
$PROFILE.CurrentUserCurrentHost # Current user, current host
$PROFILE.AllUsersCurrentHost    # All users, current host

# Create/edit profile
if (-not (Test-Path $PROFILE)) {
    New-Item -Path $PROFILE -Type File -Force
}
notepad $PROFILE

# Common profile content
# Prompt function
function prompt {
    $env:COMPUTERNAME + "\" + (Get-Location) + "> "
}

# Aliases
Set-Alias -Name gci -Value Get-ChildItem
Set-Alias -Name ll -Value Get-ChildItem

# Completions (PSReadLine)
Import-Module PSReadLine
Set-PSReadLineOption -PredictiveViewSource History
Set-PSReadLineOption -EditMode Windows
```

## Essential Modules
```powershell
# Install from PSGallery
Install-Module -Name PSReadLine -Force -SkipPublisherCheck
Install-Module -Name Terminal-Icons -Force
Install-Module -Name posh-git -Force
Install-Module -Name PSFzf -Force
Install-Module -Name InvokeBuild -Force
Install-Module -Name PSScriptAnalyzer -Force
Install-Module -Name Pester -Force -SkipPublisherCheck

# Module management
Get-InstalledModule                    # List installed modules
Update-Module -Name PSReadLine         # Update a module
Uninstall-Module -Name OldModule       # Remove a module
Find-Module -Name *git* -Repository PSGallery  # Search gallery
```

## VS Code Setup
```json
// settings.json
{
    "powershell.codeFormatting.preset": "OTBS",
    "powershell.codeFormatting.useConstantStrings": true,
    "powershell.codeFormatting.useCorrectCasing": true,
    "powershell.integratedConsole.enableConsoleRepl": true,
    "powershell.scriptAnalysis.enable": true,
    "editor.formatOnSave": true,
    "[powershell]": {
        "editor.tabSize": 4,
        "editor.insertSpaces": true
    }
}
```

### Recommended Extensions
- PowerShell (ms-vscode.powershell)
- PowerShell Preview (ms-vscode.powershell-preview)
- Code Spell Checker
- Error Lens
