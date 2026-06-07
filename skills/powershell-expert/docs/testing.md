# PowerShell Testing with Pester

## Pester v5 Structure

```powershell
# Test file: MyModule.Tests.ps1
BeforeAll {
    # Import module once
    Import-Module "$PSScriptRoot/MyModule.psm1" -Force
}

Describe 'ModuleName' {
    BeforeEach {
        # Runs before each It block
        $testPath = Join-Path $TestDrive 'testfile.txt'
        Set-Content -Path $testPath -Value 'test data'
    }

    AfterEach {
        # Cleanup after each It block
    }

    Context 'When condition is met' {
        BeforeEach {
            # Context-specific setup
        }

        It 'Should do something expected' {
            $result = Get-Something -Path $testPath
            $result | Should -Not -BeNullOrEmpty
        }

        It 'Should return correct type' {
            $result = Get-Something -Path $testPath
            $result | Should -BeOfType [PSCustomObject]
        }
    }

    Context 'When condition is not met' {
        It 'Should handle missing input' {
            { Get-Something -Path 'nonexistent' -ErrorAction Stop } |
                Should -Throw '*not found*'
        }
    }

    AfterAll {
        # Runs once after all tests
    }
}
```

## Assertions (Should)

```powershell
# Equality
$result | Should -Be 42
$result | Should -BeExactly "hello"  # Case-sensitive
$result | Should -Not -Be $null

# Type
$result | Should -BeOfType [string]
$result | Should -BeExactlyOfType [int]

# Collection
@($item1, $item2) | Should -HaveCount 2
@($item1, $item2) | Should -Contain $item1
@($item1, $item2) | Should -Not -BeNullOrEmpty

# String
"hello world" | Should -BeLike "hello*"     # Wildcard
"hello world" | Should -Match "hello \w+"   # Regex
"hello world" | Should -HaveLength 11
"HELLO" | Should -BeExactly "hello"         # Case-sensitive

# File system
Test-Path $file | Should -BeTrue
$file | Should -Exist
(Get-Item $file).Length | Should -BeGreaterThan 0

# Comparison
$result | Should -BeGreaterThan 10
$result | Should -BeLessThan 100
$result | Should -BeIn 1..10

# Errors
{ throw "error" } | Should -Throw
{ throw "error" } | Should -Throw "error"
{ throw "error" } | Should -Throw -ExceptionType [System.InvalidOperationException]
{ throw "error" } | Should -Throw '*pattern*'

# Custom assertions
$result | Should -Satisfy { $_.Name -like "Test*" }
```

## Mocking

```powershell
Describe 'Get-ServerStatus' {
    BeforeEach {
        # Mock external cmdlets
        Mock Get-Service {
            @(
                [PSCustomObject]@{ Name = 'W3SVC'; Status = 'Running' }
                [PSCustomObject]@{ Name = 'Spooler'; Status = 'Stopped' }
            )
        }

        Mock Get-Content { '{"key": "value"}' }
    }

    It 'Should call Get-Service once' {
        Get-ServerStatus -ComputerName 'localhost'
        Should -Invoke Get-Service -Times 1 -Exactly
    }

    It 'Should filter results correctly' {
        $result = Get-ServerStatus -ComputerName 'localhost' -Status 'Running'
        $result | Should -HaveCount 1
        $result.Name | Should -Be 'W3SVC'
    }

    It 'Should handle mock with parameter filter' {
        Mock Get-Service { } -ParameterFilter { $Name -eq 'W3SVC' }
        Get-ServerStatus -ComputerName 'localhost' -ServiceName 'W3SVC'
        Should -Invoke Get-Service -ParameterFilter { $Name -eq 'W3SVC' } -Times 1
    }

    It 'Should verify mock was called with specific parameters' {
        Mock Invoke-RestMethod { @{ status = 'ok' } }
        Invoke-WithRetry -Uri "https://api.example.com" -MaxRetries 3
        Should -Invoke Invoke-RestMethod -Times 3
    }
}
```

## Test Data & In-Memory Drives

```powershell
Describe 'File operations' {
    BeforeEach {
        # Create temp files using TestDrive
        "file1.txt" | Out-File (Join-Path $TestDrive 'file1.txt')
        "file2.txt" | Out-File (Join-Path $TestDrive 'file2.txt')
    }

    It 'Should process all files' {
        $files = Get-ChildItem -Path $TestDrive -File
        $files | Should -HaveCount 2
    }

    It 'Should read file content' {
        $content = Get-Content (Join-Path $TestDrive 'file1.txt') -Raw
        $content | Should -Be 'file1.txt'
    }
}
```

## Running Tests

```powershell
# Run all tests in current directory
Invoke-Pester

# Run specific test file
Invoke-Pester -Path .\MyModule.Tests.ps1

# Run with output
Invoke-Pester -Output Detailed

# Run with code coverage
Invoke-Pester -CodeCoverage .\MyModule.psm1 -CodeCoverageOutputFile .\coverage.xml

# Run specific tests by tag
Invoke-Pester -Tag 'Integration'

# CI/CD integration
Invoke-Pester -Output.xml .\Tests -OutputFormat NUnitXml
```
