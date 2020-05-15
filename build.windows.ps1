#$ErrorActionPreference = 'Stop'

$env:GIT_REDIRECT_STDERR = '2>&1'

$SCRIPT_DIR = (Resolve-Path ".").Path

$VERSION_FILE = Join-Path (Resolve-Path ".").Path "VERSION"
Get-Content $VERSION_FILE | Foreach-Object{
  $var = $_.Split('=')
  New-Variable -Name $var[0] -Value $var[1]
}

$PACKAGE_NAME = "windows"
$SOURCE_DIR = Join-Path (Resolve-Path ".").Path "_source\$PACKAGE_NAME"
$BUILD_DIR = Join-Path (Resolve-Path ".").Path "_build\$PACKAGE_NAME"
$PACKAGE_DIR = Join-Path (Resolve-Path ".").Path "_package\$PACKAGE_NAME"

if (!(Test-Path $BUILD_DIR)) {
  mkdir $BUILD_DIR
}

if (!(Test-Path $BUILD_DIR\vswhere.exe)) {
  Invoke-WebRequest -Uri "https://github.com/microsoft/vswhere/releases/download/2.8.4/vswhere.exe" -OutFile $BUILD_DIR\vswhere.exe
}

# vsdevcmd.bat の設定を入れる
# https://github.com/microsoft/vswhere/wiki/Find-VC
Push-Location $BUILD_DIR
  $path = .\vswhere.exe -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
Pop-Location
if ($path) {
  $path = Join-Path $path 'Common7\Tools\vsdevcmd.bat'
  if (Test-Path $path) {
    cmd /s /c """$path"" $args && set" | Where-Object { $_ -match '(\w+)=(.*)' } | ForEach-Object {
      $null = New-Item -force -path "Env:\$($Matches[1])" -value $Matches[2]
    }
  }
}

# $SOURCE_DIR の下に置きたいが、webrtc のパスが長すぎると動かない問題と、
# GitHub Actions の D:\ の容量が少なくてビルド出来ない問題があるので
# このパスにソースを配置する
$WEBRTC_DIR = "C:\webrtc"
# また、WebRTC のビルドしたファイルは同じドライブに無いといけないっぽいので、
# BUILD_DIR とは別で用意する
$WEBRTC_BUILD_DIR = "C:\webrtc_build"

# WebRTC ビルドに必要な環境変数の設定
$Env:GYP_MSVS_VERSION = "2019"
$Env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"
$Env:PYTHONIOENCODING = "utf-8"

if (!(Test-Path $SOURCE_DIR)) {
  New-Item -ItemType Directory -Path $SOURCE_DIR
}

# depot_tools
if (!(Test-Path $SOURCE_DIR\depot_tools)) {
  Push-Location $SOURCE_DIR
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
  Pop-Location
} else {
  Push-Location $SOURCE_DIR\depot_tools
    git fetch
    git checkout -f origin/HEAD
  Pop-Location
}

$Env:PATH = "$SOURCE_DIR\depot_tools;$Env:PATH"
# Choco へのパスを削除
$Env:PATH = $Env:Path.Replace("C:\ProgramData\Chocolatey\bin;", "");

# WebRTC のソース取得
if (!(Test-Path $WEBRTC_DIR)) {
  mkdir $WEBRTC_DIR
}
if (!(Test-Path $WEBRTC_DIR\src)) {
  Push-Location $WEBRTC_DIR
    gclient
    fetch webrtc
  Pop-Location
} else {
  Push-Location $WEBRTC_DIR\src
    git clean -xdf
    git reset --hard
    Push-Location build
      git reset --hard
    Pop-Location
    Push-Location third_party
      git reset --hard
    Pop-Location
    git fetch
  Pop-Location
}

if (!(Test-Path $WEBRTC_BUILD_DIR)) {
  mkdir $WEBRTC_BUILD_DIR
}
Push-Location $WEBRTC_DIR\src
  git checkout -f "$WEBRTC_COMMIT"
  git clean -xdf
  gclient sync

  # patch の適用
  git apply -p2 --ignore-space-change --ignore-whitespace --whitespace=nowarn $SCRIPT_DIR\patches\4k.patch
  if (!$?) {
    exit 1
  }

  # WebRTC ビルド
  gn gen $WEBRTC_BUILD_DIR\debug --args='is_debug=true rtc_include_tests=false rtc_use_h264=false is_component_build=false use_rtti=true use_custom_libcxx=false'
  ninja -C "$WEBRTC_BUILD_DIR\debug"

  gn gen $WEBRTC_BUILD_DIR\release --args='is_debug=false rtc_include_tests=false rtc_use_h264=false is_component_build=false use_rtti=true use_custom_libcxx=false'
  ninja -C "$WEBRTC_BUILD_DIR\release"
Pop-Location

foreach ($build in @("debug", "release")) {
  ninja -C "$WEBRTC_BUILD_DIR\$build" audio_device_module_from_input_and_output

  # このままだと webrtc.lib に含まれないファイルがあるので、いくつか追加する
  Push-Location $WEBRTC_BUILD_DIR\$build\obj
    lib.exe `
      /out:$WEBRTC_BUILD_DIR\$build\webrtc.lib webrtc.lib `
      api\task_queue\default_task_queue_factory\default_task_queue_factory_win.obj `
      rtc_base\rtc_task_queue_win\task_queue_win.obj `
      modules\audio_device\audio_device_module_from_input_and_output\audio_device_factory.obj `
      modules\audio_device\audio_device_module_from_input_and_output\audio_device_module_win.obj `
      modules\audio_device\audio_device_module_from_input_and_output\core_audio_base_win.obj `
      modules\audio_device\audio_device_module_from_input_and_output\core_audio_input_win.obj `
      modules\audio_device\audio_device_module_from_input_and_output\core_audio_output_win.obj `
      modules\audio_device\windows_core_audio_utility\core_audio_utility_win.obj `
      modules\audio_device\audio_device_name\audio_device_name.obj
  Pop-Location
  Move-Item $WEBRTC_BUILD_DIR\$build\webrtc.lib $WEBRTC_BUILD_DIR\$build\obj\webrtc.lib -Force
}

# ライセンス生成
Push-Location $WEBRTC_DIR\src
  python2 tools_webrtc\libs\generate_licenses.py --target :webrtc "$WEBRTC_BUILD_DIR\" "$WEBRTC_BUILD_DIR\debug" "$WEBRTC_BUILD_DIR\release"
Pop-Location


# WebRTC のヘッダーをパッケージに含める
if (Test-Path $BUILD_DIR\package) {
  Remove-Item -Force -Recurse -Path $BUILD_DIR\package
}
mkdir $BUILD_DIR\package
mkdir $BUILD_DIR\package\webrtc
robocopy "$WEBRTC_DIR\src" "$BUILD_DIR\package\webrtc\include" *.h *.hpp /S /NP /NFL /NDL

# webrtc.lib をパッケージに含める
foreach ($build in @("debug", "release")) {
  mkdir $BUILD_DIR\package\webrtc\$build
  Copy-Item $WEBRTC_BUILD_DIR\$build\obj\webrtc.lib $BUILD_DIR\package\webrtc\$build\
}

# ライセンスファイルをパッケージに含める
Copy-Item "$WEBRTC_BUILD_DIR\LICENSE.md" "$BUILD_DIR\package\webrtc\NOTICE"

# WebRTC の各種バージョンをパッケージに含める
Copy-Item $VERSION_FILE $BUILD_DIR\package\webrtc\VERSIONS
Push-Location $WEBRTC_DIR\src
  Write-Output "WEBRTC_SRC_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\build
  Write-Output "WEBRTC_SRC_BUILD_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_BUILD_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\buildtools
  Write-Output "WEBRTC_SRC_BUILDTOOLS_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_BUILDTOOLS_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\buildtools\third_party\libc++\trunk
  # 後方互換性のために残す。どこかで消す
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8

  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\buildtools\third_party\libc++abi\trunk
  # 後方互換性のために残す。どこかで消す
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8

  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\buildtools\third_party\libunwind\trunk
  # 後方互換性のために残す。どこかで消す
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8

  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\third_party
  Write-Output "WEBRTC_SRC_THIRD_PARTY_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_THIRD_PARTY_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location
Push-Location $WEBRTC_DIR\src\tools
  Write-Output "WEBRTC_SRC_TOOLS_COMMIT=$(git rev-parse HEAD)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
  Write-Output "WEBRTC_SRC_TOOLS_URL=$(git remote get-url origin)" | Add-Content $BUILD_DIR\package\webrtc\VERSIONS -Encoding UTF8
Pop-Location

# まとめて zip にする
if (!(Test-Path $PACKAGE_DIR)) {
  mkdir $PACKAGE_DIR
}
if (Test-Path $PACKAGE_DIR\webrtc.zip) {
  Remove-Item -Force -Path $PACKAGE_DIR\webrtc.zip
}
Push-Location $BUILD_DIR\package
  7z a $PACKAGE_DIR\webrtc.zip webrtc
  # 7z に失敗したら Compress-Archive を使う
  if (!$?) {
    Compress-Archive -DestinationPath $PACKAGE_DIR\webrtc.zip -Path webrtc -Force
  }
Pop-Location
