[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $InstancePath,
    [Parameter(Mandatory = $true)]
    [string] $BootstrapJar,
    [string] $Java = 'java',
    [string] $Tag,
    [string] $Minecraft = '26.3',
    [string] $Fabric = '0.20.1'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Install-ClientDefaults($Archive, $Instance) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $parts = $entry.FullName.Split('/')
            if ($parts.Count -lt 2 -or $parts[0] -notin @('config', 'defaultconfigs') -or
                ($parts | Where-Object { $_ -match '^\.{0,2}$|[\\:<>|?*"\x00-\x1f]' })) {
                throw "Unexpected path in client defaults: $($entry.FullName)"
            }
            $target = $Instance
            foreach ($part in $parts) {
                $target = Join-Path $target $part
                if ((Test-Path -LiteralPath $target) -and
                    ((Get-Item -LiteralPath $target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                    throw "A client default points to a link: $target"
                }
            }
            if (!(Test-Path -LiteralPath $target)) {
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
            }
        }
    }
    finally { $zip.Dispose() }
}

if ($MyInvocation.InvocationName -eq '.') { return }

$releaseRoot = 'https://github.com/swiizyy/our-little-world/releases'
$tagPattern = '^v\d+\.\d+\.\d+(?:-(?:alpha|beta)(?:\.[0-9A-Za-z-]+)*)?\z'
if ($Tag) {
    if ($Tag -cnotmatch $tagPattern) {
        throw "Invalid release tag: $Tag"
    }
    $assets = "$releaseRoot/download/$Tag"
}
else { $assets = "$releaseRoot/latest/download" }

$instance = (Get-Item -LiteralPath $InstancePath).FullName
if (!(Test-Path -LiteralPath $instance -PathType Container)) { throw 'Select a dedicated Minecraft Fabric game directory.' }
$bootstrap = (Get-Item -LiteralPath $BootstrapJar).FullName
$temporary = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
[IO.Directory]::CreateDirectory($temporary) | Out-Null
try {
    $manifestFile = Join-Path $temporary 'pack-manifest.json'
    Invoke-WebRequest -UseBasicParsing "$assets/pack-manifest.json" -OutFile $manifestFile
    $manifest = Get-Content -Raw -LiteralPath $manifestFile | ConvertFrom-Json
    if ($manifest.tag -cnotmatch $tagPattern -or $manifest.tag -cne "v$($manifest.version)" -or
        ($Tag -and $manifest.tag -cne $Tag) -or (!$Tag -and $manifest.channel -cne 'release') -or
        $manifest.versions.minecraft -cne $Minecraft -or $manifest.versions.fabric -cne $Fabric -or
        $manifest.commit -cnotmatch '^[0-9a-f]{40}\z' -or
        $manifest.packwiz_url -cne "https://raw.githubusercontent.com/swiizyy/our-little-world/$($manifest.commit)/pack.toml") {
        throw 'The release does not match this instance. Check the release tag, Minecraft and Fabric versions.'
    }

    $pack = Join-Path $temporary 'pack.toml'
    Invoke-WebRequest -UseBasicParsing $manifest.packwiz_url -OutFile $pack
    if ((Get-FileHash -LiteralPath $pack -Algorithm SHA256).Hash -ne $manifest.packwiz_sha256) {
        throw 'Release pack.toml failed SHA-256 verification.'
    }
    $defaults = Join-Path $temporary 'client-defaults.zip'
    Invoke-WebRequest -UseBasicParsing "$releaseRoot/download/$($manifest.tag)/client-defaults.zip" -OutFile $defaults
    if ((Get-FileHash -LiteralPath $defaults -Algorithm SHA256).Hash -ne $manifest.client_defaults_sha256) {
        throw 'Release client defaults failed SHA-256 verification.'
    }

    $lock = [IO.File]::Open((Join-Path $instance '.olw-sync.lock'), 'OpenOrCreate', 'Write', 'None')
    try {
        Push-Location -LiteralPath $instance
        try {
            # The installer cache tracks ownership of files between launches.
            if (!(Test-Path -LiteralPath 'packwiz.json') -and
                (Test-Path -LiteralPath 'mods') -and
                (Get-ChildItem -LiteralPath 'mods' -File -Force | Select-Object -First 1)) {
                throw 'Use a fresh Fabric instance for the first Packwiz run. Existing mods have no Packwiz ownership record.'
            }
            & $Java -jar $bootstrap -g -s client $manifest.packwiz_url
            if ($LASTEXITCODE -ne 0) { throw "Packwiz Installer exited with code $LASTEXITCODE." }
            Install-ClientDefaults $defaults $instance
            Write-Output "Our Little World $($manifest.version) synchronized."
        }
        finally { Pop-Location }
    }
    finally { $lock.Dispose() }
}
finally {
    # All downloaded scratch files were created in this private temporary folder.
    foreach ($name in @('pack-manifest.json', 'pack.toml', 'client-defaults.zip')) {
        [IO.File]::Delete((Join-Path $temporary $name))
    }
    [IO.Directory]::Delete($temporary)
}
