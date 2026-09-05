$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$log = Join-Path $repo "logs\auto-sync.log"
$debounceSeconds = 30

New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Write-Log([string]$message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message
    Add-Content -Path $log -Value $line
}

function Invoke-Git([string[]]$arguments) {
    $output = & git -C $repo @arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (($output -join [Environment]::NewLine).Trim())
    }
    return $output
}

function Sync-Repository {
    try {
        $status = @(Invoke-Git @("status", "--porcelain"))
        if ($status.Count -eq 0) {
            return
        }

        Invoke-Git @("add", "-A") | Out-Null
        $message = "Sincronizacao automatica $(Get-Date -Format "yyyy-MM-dd HH:mm")"
        Invoke-Git @("commit", "-m", $message, "-m", "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>") | Out-Null
        Invoke-Git @("pull", "--rebase", "--autostash", "origin", "master") | Out-Null
        Invoke-Git @("push", "origin", "master") | Out-Null
        Write-Log "Sincronizacao concluida."
    }
    catch {
        Write-Log "Falha na sincronizacao: $($_.Exception.Message)"
    }
}

Write-Log "Monitor iniciado."
$watcher = New-Object IO.FileSystemWatcher
$watcher.Path = $repo
$watcher.IncludeSubdirectories = $true
$watcher.NotifyFilter = [IO.NotifyFilters]::FileName -bor [IO.NotifyFilters]::LastWrite -bor [IO.NotifyFilters]::DirectoryName
$watcher.EnableRaisingEvents = $true

$lastChange = [DateTime]::MinValue
$action = {
    $relative = $EventArgs.FullPath.Substring($repo.Length).TrimStart("\")
    if ($relative -notmatch '^(?:\.git|\.venv|build|dist|logs|backups|\.pytest_cache)(?:\\|$)') {
        $script:lastChange = Get-Date
    }
}

Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action | Out-Null
Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action | Out-Null
Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $action | Out-Null
Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $action | Out-Null

try {
    while ($true) {
        Start-Sleep -Seconds 5
        if ($lastChange -ne [DateTime]::MinValue -and ((Get-Date) - $lastChange).TotalSeconds -ge $debounceSeconds) {
            $lastChange = [DateTime]::MinValue
            Sync-Repository
        }
    }
}
finally {
    $watcher.Dispose()
    Unregister-Event -SourceIdentifier *
}
