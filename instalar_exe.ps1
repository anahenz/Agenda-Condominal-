$ErrorActionPreference = 'Stop'
try {
    $sourceExe = Join-Path $PSScriptRoot 'dist\AgendaCondominial.exe'
    if (-not (Test-Path $sourceExe)) { throw 'Gere o executavel primeiro com gerar_exe.bat.' }
    $installDir = Join-Path $env:LOCALAPPDATA 'Programs\AgendaCondominial'
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    $targetExe = Join-Path $installDir 'AgendaCondominial.exe'
    Copy-Item -LiteralPath $sourceExe -Destination $targetExe -Force
    $shell = New-Object -ComObject WScript.Shell
    $shortcutDirs = @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))
    foreach ($shortcutDir in $shortcutDirs) {
        $shortcut = $shell.CreateShortcut((Join-Path $shortcutDir 'AgendaCondominial.lnk'))
        $shortcut.TargetPath = $targetExe
        $shortcut.WorkingDirectory = $installDir
        $shortcut.IconLocation = "$targetExe,0"
        $shortcut.Save()
    }
    Write-Host "Instalado em $installDir. Abra pelo atalho AgendaCondominial."
} catch {
    Write-Host "Falha ao instalar: $($_.Exception.Message)"
    exit 1
}
