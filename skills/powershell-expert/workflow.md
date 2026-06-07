# PowerShell Development Workflow

## 1. Inspect
- Read the target .ps1, .psm1, or .psd1 files
- Check the module manifest for version, dependencies, exported functions
- Review any existing Pester tests
- Identify PowerShell version requirements ($PSVersionTable)
- Check for installed modules (Get-Module -ListAvailable)

## 2. Analyze
- Understand the script's purpose and pipeline flow
- Identify cmdlets used and their parameters
- Review error handling patterns
- Check for security concerns (credentials, secrets, execution policy)
- Look for performance bottlenecks (pipeline vs. loop, large data)
- Verify approved verb usage

## 3. Plan
- Design the solution following PowerShell best practices
- Consider pipeline input/output compatibility
- Plan error handling strategy (terminating vs. non-terminating)
- Decide on parameter validation approach
- Plan for -WhatIf/-Confirm support on destructive ops
- Document the approach

## 4. Implement
- Write clean, idiomatic PowerShell code
- Use [CmdletBinding()] and proper parameter attributes
- Add comment-based help
- Handle errors with try/catch or -ErrorAction
- Use pipeline-native patterns
- Follow PowerShell style guidelines

## 5. Test
- Write Pester v5+ tests
- Use Mock for external dependencies
- Test pipeline input
- Test error conditions
- Test -WhatIf behavior
- Validate parameter sets

## 6. Verify
- Run Pester tests (Invoke-Pester)
- Check for script analysis warnings (Invoke-ScriptAnalyzer)
- Verify execution policy compatibility
- Test on target PowerShell version
- Review for security issues
