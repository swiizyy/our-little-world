$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../client/Sync-OurLittleWorld.ps1') -InstancePath '.' -BootstrapJar 'unused'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression

$workspace = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
$instance = Join-Path $workspace 'Instance with spaces'
$archive = Join-Path $workspace 'client-defaults.zip'

function Write-DefaultArchive($Path, $Name) {
    $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $writer = [IO.StreamWriter]::new($zip.CreateEntry($Name).Open())
        try { $writer.Write('pack default') }
        finally { $writer.Dispose() }
    }
    finally { $zip.Dispose() }
}

try {
    [IO.Directory]::CreateDirectory($instance) | Out-Null
    Write-DefaultArchive $archive 'config/example.cfg'
    Install-ClientDefaults $archive $instance
    $target = Join-Path $instance 'config/example.cfg'
    if ([IO.File]::ReadAllText($target) -ne 'pack default') { throw 'Default was not installed' }
    [IO.File]::WriteAllText($target, 'my preference')
    Install-ClientDefaults $archive $instance
    if ([IO.File]::ReadAllText($target) -ne 'my preference') { throw 'Personal preference was replaced' }

    $invalid = Join-Path $workspace 'invalid.zip'
    Write-DefaultArchive $invalid 'config/../../options.txt'
    try {
        Install-ClientDefaults $invalid $instance
        throw 'Unexpected success'
    }
    catch {
        if ($_.Exception.Message -notlike 'Unexpected path in client defaults:*') { throw }
    }
    Write-Output 'Client defaults tests passed.'
}
finally {
    $resolved = (Resolve-Path -LiteralPath $workspace).Path
    if ($resolved -eq $workspace) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
