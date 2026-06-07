# PowerShell Examples

## Advanced Function with Pipeline Support

```powershell
function Get-ServerStatus {
    <#
    .SYNOPSIS
        Gets the status of services on one or more servers.
    .DESCRIPTION
        Retrieves service status from remote servers using PowerShell remoting.
    .PARAMETER ComputerName
        One or more computer names to query.
    .PARAMETER ServiceName
        Optional service name filter.
    .EXAMPLE
        Get-ServerStatus -ComputerName "SRV01","SRV02" -ServiceName "W3SVC"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('Name', 'PSComputerName')]
        [string[]]$ComputerName,

        [Parameter()]
        [ValidateNotNullOrEmpty()]
        [string]$ServiceName,

        [Parameter()]
        [ValidateSet('Running', 'Stopped', 'Paused')]
        [string]$Status
    )

    process {
        foreach ($computer in $ComputerName) {
            Write-Verbose "Querying $computer..."
            try {
                $services = Get-Service -ComputerName $computer -ErrorAction Stop |
                    Where-Object {
                        (-not $ServiceName -or $_.Name -like $ServiceName) -and
                        (-not $Status -or $_.Status -eq $Status)
                    }
                foreach ($svc in $services) {
                    [PSCustomObject]@{
                        ComputerName = $computer
                        Name         = $svc.Name
                        DisplayName  = $svc.DisplayName
                        Status       = $svc.Status
                    }
                }
            }
            catch {
                Write-Error "Failed to query $computer: $_"
            }
        }
    }
}
```

## Error Handling Pattern

```powershell
function Set-ApplicationConfig {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [hashtable]$Settings
    )

    begin {
        $ErrorActionPreference = 'Stop'
    }

    process {
        if (-not $PSCmdlet.ShouldProcess($Path, 'Update configuration')) {
            return
        }

        try {
            $config = Get-Content -Path $Path -Raw | ConvertFrom-Json

            foreach ($key in $Settings.Keys) {
                $config.$key = $Settings[$key]
            }

            $config | ConvertTo-Json -Depth 10 | Set-Content -Path $Path -Encoding UTF8
            Write-Verbose "Configuration updated: $Path"
        }
        catch [System.IO.FileNotFoundException] {
            Write-Error "Config file not found: $Path"
        }
        catch [System.UnauthorizedAccessException] {
            Write-Error "Access denied: $Path"
        }
        catch {
            Write-Error "Failed to update config: $_"
        }
    }
}
```

## Module Manifest (.psd1)

```powershell
@{
    RootModule        = 'MyModule.psm1'
    ModuleVersion     = '1.0.0'
    GUID              = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    Author            = 'Your Name'
    CompanyName       = 'Your Company'
    Copyright         = '(c) 2026. All rights reserved.'
    Description       = 'A PowerShell module for automation tasks.'
    PowerShellVersion = '5.1'
    RequiredModules   = @(
        @{ ModuleName = 'PSFramework'; ModuleVersion = '1.10.0' }
    )
    FunctionsToExport = @(
        'Get-MyData'
        'Set-MyData'
        'Remove-MyData'
    )
    CmdletsToExport   = @()
    VariablesToExport  = @()
    AliasesToExport    = @()
    PrivateData = @{
        PSData = @{
            Tags       = @('automation', 'devops')
            LicenseUri = 'https://opensource.org/licenses/MIT'
            ProjectUri = 'https://github.com/yourname/yourmodule'
        }
    }
}
```

## Pester Test

```powershell
BeforeAll {
    Import-Module "$PSScriptRoot/../MyModule.psm1" -Force
}

Describe 'Get-ServerStatus' {
    Context 'When services exist' {
        BeforeEach {
            Mock Get-Service {
                @(
                    [PSCustomObject]@{ Name = 'W3SVC'; DisplayName = 'World Wide Web'; Status = 'Running' }
                    [PSCustomObject]@{ Name = 'Spooler'; DisplayName = 'Print Spooler'; Status = 'Stopped' }
                )
            }
        }

        It 'Should return all services when no filter' {
            $result = Get-ServerStatus -ComputerName 'localhost'
            $result | Should -HaveCount 2
        }

        It 'Should filter by service name' {
            $result = Get-ServerStatus -ComputerName 'localhost' -ServiceName 'W3SVC'
            $result | Should -HaveCount 1
            $result.Name | Should -Be 'W3SVC'
        }

        It 'Should filter by status' {
            $result = Get-ServerStatus -ComputerName 'localhost' -Status 'Running'
            $result | Should -HaveCount 1
            $result.Status | Should -Be 'Running'
        }
    }

    Context 'When computer is unreachable' {
        BeforeEach {
            Mock Get-Service { throw 'Unable to connect' }
        }

        It 'Should write an error' {
            { Get-ServerStatus -ComputerName 'badhost' -ErrorAction Stop } |
                Should -Throw '*Failed to query*'
        }
    }
}
```

## Scheduled Task Automation

```powershell
function Register-DailyCleanupTask {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [string]$TaskName,

        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter()]
        [int]$RetentionDays = 30,

        [Parameter()]
        [string]$Time = '02:00'
    )

    $action = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument @(
        "-NoProfile -NonInteractive -Command `"",
        "Get-ChildItem -Path '$Path' -Recurse -File |",
        "Where-Object { `$_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |",
        "Remove-Item -Force`""
    ) -WorkingDirectory $Path

    $trigger = New-ScheduledTaskTrigger -Daily -At $Time

    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

    if ($PSCmdlet.ShouldProcess($TaskName, 'Register scheduled task')) {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $Settings -Force
    }
}
```

## Azure PowerShell Automation

```powershell
function Get-AzureResourceCost {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ResourceGroup,

        [Parameter()]
        [int]$Days = 7
    )

    $startDate = (Get-Date).AddDays(-$Days).ToString('yyyy-MM-dd')
    $endDate = (Get-Date).ToString('yyyy-MM-dd')

    Get-AzCostAnalysis -ResourceGroupName $ResourceGroup -StartTime $startDate -EndTime $endDate |
        Group-Object ResourceGroup |
        ForEach-Object {
            [PSCustomObject]@{
                ResourceGroup = $_.Name
                TotalCost     = ($_.Group | Measure-Object PreTaxCost -Sum).Sum
                Currency      = $_.Group[0].Currency
                Period        = "$startDate to $endDate"
            }
        }
}
```
