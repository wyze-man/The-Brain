[app]
title = Big Brain AI
package.name = bigbrain
package.domain = org.bigbrain
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

# pillow for image rendering, requests removed — kernel uses urllib only
requirements = python3,kivy==2.3.0,pillow

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO
android.api = 33
android.minapi = 26
android.ndk = 25
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True
android.build_tools_version = 34.0.0
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.2.9519653

[buildozer]
log_level = 2
warn_on_root = 1
