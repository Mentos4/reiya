[app]
title = Reiya Account Manager
package.name = reiyaaccountmanager
package.domain = org.reiya
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy,pyjnius,android,requests,certifi,charset-normalizer,idna,urllib3

orientation = portrait
fullscreen = 0

android.minapi = 21
android.api = 33
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,QUERY_ALL_PACKAGES,PACKAGE_USAGE_STATS,FOREGROUND_SERVICE

p4a.hook = buildozer_hook.py

[buildozer]
log_level = 2
warn_on_root = 1
