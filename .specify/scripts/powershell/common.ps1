#!/usr/bin/env pwsh
# Common PowerShell functions analogous to common.sh

function Get-RepoRoot {
    try {
        $result = git rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $result
        }
    } catch {
        # Git command failed
    }
    
    # Fall back to script location for non-git repos
    return (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
}

function Get-CurrentBranch {
    # First check if SPECIFY_FEATURE environment variable is set
    if ($env:SPECIFY_FEATURE) {
        return $env:SPECIFY_FEATURE
    }
    
    # Then check git if available
    try {
        $result = git rev-parse --abbrev-ref HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $result
        }
    } catch {
        # Git command failed
    }
    
    # For non-git repos, try to find the latest feature directory
    $repoRoot = Get-RepoRoot
    $specsDir = Join-Path $repoRoot "specs"
    
    if (Test-Path $specsDir) {
        $latestFeature = ""
        $highest = 0
        
        Get-ChildItem -Path $specsDir -Directory | ForEach-Object {
            if ($_.Name -match '^(\d{3})-') {
                $num = [int]$matches[1]
                if ($num -gt $highest) {
                    $highest = $num
                    $latestFeature = $_.Name
                }
            }
        }
        
        if ($latestFeature) {
            return $latestFeature
        }
    }
    
    # Final fallback
    return "main"
}

function Test-HasGit {
    try {
        git rev-parse --show-toplevel 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-LatestSpecDir {
    param([string]$SpecsDir)

    if (-not (Test-Path $SpecsDir)) {
        return $null
    }

    $latest = Get-ChildItem -Path $SpecsDir -Directory |
        Where-Object { $_.Name -match '^(\d{3})-' } |
        Sort-Object { [int]$_.Name.Substring(0, 3) } -Descending |
        Select-Object -First 1

    if ($latest) {
        return $latest.FullName
    }

    return $null
}

function Find-FeatureDirByTaskId {
    param(
        [string]$RepoRoot,
        [string]$TaskId
    )

    $specsDir = Join-Path $RepoRoot 'specs'
    if (-not (Test-Path $specsDir)) {
        return $null
    }

    $normalizedTaskId = $TaskId.ToUpper()
    $matches = Get-ChildItem -Path $specsDir -Recurse -Filter tasks.md -File -ErrorAction SilentlyContinue |
        Where-Object {
            Select-String -Path $_.FullName -Pattern "\b$normalizedTaskId\b" -Quiet
        } |
        ForEach-Object { Split-Path $_.FullName -Parent }

    if ($matches.Count -eq 1) {
        return $matches[0]
    }

    if ($matches.Count -gt 1) {
        Write-Error "Multiple spec directories contain task '$normalizedTaskId': $($matches -join ', ')"
    }

    return $null
}

function Test-FeatureBranch {
    param(
        [string]$Branch,
        [bool]$HasGit = $true
    )
    
    # For non-git repos, we can't enforce branch naming but still provide output
    if (-not $HasGit) {
        Write-Warning "[specify] Warning: Git repository not detected; skipped branch validation"
        return $true
    }
    
    if (($Branch -ne 'dev') -and ($Branch -notmatch '^feature/[a-zA-Z0-9._-]+$')) {
        Write-Output "ERROR: Not on a feature branch. Current branch: $Branch"
        Write-Output "Feature branches should be named like: feature/t006-test-fixtures or feature/123-session-cleanup (or 'dev')"
        return $false
    }
    return $true
}

function Get-FeatureDir {
    param([string]$RepoRoot, [string]$Branch)
    Join-Path $RepoRoot "specs/$Branch"
}

function Get-FeaturePathsEnv {
    $repoRoot = Get-RepoRoot
    $currentBranch = Get-CurrentBranch
    $hasGit = Test-HasGit

    $specsDir = Join-Path $repoRoot 'specs'
    $branchRef = $currentBranch
    if ($branchRef -match '^feature/(.+)$') {
        $branchRef = $matches[1]
    }

    $featureDir = $null
    if ($branchRef -match '^(t\d+)-') {
        $featureDir = Find-FeatureDirByTaskId -RepoRoot $repoRoot -TaskId $matches[1]
    }

    if (-not $featureDir -and $branchRef -match '^(\d{3})-') {
        $prefix = $matches[1]
        $matchingDir = Get-ChildItem -Path $specsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^$prefix-" } |
            Select-Object -First 1
        if ($matchingDir) {
            $featureDir = $matchingDir.FullName
        }
    }

    if (-not $featureDir -and $currentBranch -eq 'dev') {
        $featureDir = Get-LatestSpecDir -SpecsDir $specsDir
    }

    if (-not $featureDir -and (Test-Path $specsDir)) {
        $allSpecDirs = Get-ChildItem -Path $specsDir -Directory -ErrorAction SilentlyContinue
        if ($allSpecDirs.Count -eq 1) {
            $featureDir = $allSpecDirs[0].FullName
        }
    }

    if (-not $featureDir) {
        $featureDir = Get-FeatureDir -RepoRoot $repoRoot -Branch $branchRef
    }
    
    [PSCustomObject]@{
        REPO_ROOT     = $repoRoot
        CURRENT_BRANCH = $currentBranch
        HAS_GIT       = $hasGit
        FEATURE_DIR   = $featureDir
        FEATURE_SPEC  = Join-Path $featureDir 'spec.md'
        IMPL_PLAN     = Join-Path $featureDir 'plan.md'
        TASKS         = Join-Path $featureDir 'tasks.md'
        RESEARCH      = Join-Path $featureDir 'research.md'
        DATA_MODEL    = Join-Path $featureDir 'data-model.md'
        QUICKSTART    = Join-Path $featureDir 'quickstart.md'
        CONTRACTS_DIR = Join-Path $featureDir 'contracts'
    }
}

function Test-FileExists {
    param([string]$Path, [string]$Description)
    if (Test-Path -Path $Path -PathType Leaf) {
        Write-Output "  ✓ $Description"
        return $true
    } else {
        Write-Output "  ✗ $Description"
        return $false
    }
}

function Test-DirHasFiles {
    param([string]$Path, [string]$Description)
    if ((Test-Path -Path $Path -PathType Container) -and (Get-ChildItem -Path $Path -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer } | Select-Object -First 1)) {
        Write-Output "  ✓ $Description"
        return $true
    } else {
        Write-Output "  ✗ $Description"
        return $false
    }
}

