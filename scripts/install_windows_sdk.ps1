# Windows SDK 10.0.28000.0 をインストールするスクリプト。
#
# このスクリプトを追加した背景
#
# m153 で chromium build の SDK_VERSION が 10.0.28000.0 に更新されたが、
# GitHub Actions の windows runner (windows-2022) には 10.0.28000.0 が
# インストールされておらず、setup_toolchain.py が include 環境変数内の
# 10.0.28000.0 のパスが存在しないエラーを出して gn gen が失敗した。
# そのため build.yml の build-windows ジョブ (Build ステップの前) から
# 呼び出して SDK を明示的にインストールする。
#
# このスクリプトを外す条件
#
# GitHub Actions の windows runner (例: windows-2022 の更新や新しい runner
# イメージ) に Windows SDK 10.0.28000.0 が標準でインストールされるように
# なった場合は、build.yml の Install Windows SDK ステップごと削除してよい。
# なお SDK_VERSION が再び別のバージョンへ更新された場合は、このスクリプトの
# $sdkVersion (と必要に応じて各所のバージョン表記) を新しい値に更新すること。

[CmdletBinding()]
param(
    # 既にダウンロード済みのインストーラーを使う場合に指定する。
    [string]$InstallerPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sdkVersion = "10.0.28000.0"
$sdkInstallerVersion = "10.0.28000.2526"
# 公式ダウンロードページ (https://learn.microsoft.com/ja-jp/windows/apps/windows-sdk/downloads) の
# Windows SDK for Windows 11 (10.0.28000.2526) のインストーラーのリンクを使用する
$sdkInstallerUrl = "https://go.microsoft.com/fwlink/?linkid=2372508"
$windowsKitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10"
$requiredPaths = @(
    (Join-Path $windowsKitsRoot "include\$sdkVersion\um"),
    (Join-Path $windowsKitsRoot "lib\$sdkVersion\um\x64"),
    (Join-Path $windowsKitsRoot "lib\$sdkVersion\um\arm64")
)

function Test-WindowsSdkInstalled {
    foreach ($path in $requiredPaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
            return $false
        }
    }

    return $true
}

if (Test-WindowsSdkInstalled) {
    Write-Host "Windows SDK $sdkVersion is already installed."
    exit 0
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "This script must be run as Administrator."
}

if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
    $downloadDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "webrtc-build-windows-sdk"
    New-Item -ItemType Directory -Path $downloadDirectory -Force | Out-Null
    $InstallerPath = Join-Path $downloadDirectory "winsdksetup-$sdkInstallerVersion.exe"

    if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
        Write-Host "Downloading Windows SDK installer $sdkInstallerVersion..."
        Invoke-WebRequest -Uri $sdkInstallerUrl -OutFile $InstallerPath
    }
}

$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
$signature = Get-AuthenticodeSignature -FilePath $InstallerPath
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "The Windows SDK installer signature is not valid: $($signature.Status)"
}
if ($signature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "The Windows SDK installer is not signed by Microsoft: $($signature.SignerCertificate.Subject)"
}

Write-Host "Installing Windows SDK $sdkVersion..."
$processArguments = @{
    FilePath     = $InstallerPath
    ArgumentList = @("/quiet", "/norestart")
    Wait         = $true
    PassThru     = $true
}
$process = Start-Process @processArguments

if ($process.ExitCode -notin @(0, 3010)) {
    throw "Windows SDK installer failed with exit code $($process.ExitCode)."
}

if (-not (Test-WindowsSdkInstalled)) {
    $missingPaths = $requiredPaths | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Container) }
    throw "Windows SDK $sdkVersion was not installed completely. Missing paths: $($missingPaths -join ', ')"
}

Write-Host "Windows SDK $sdkVersion is installed successfully."
