@echo off
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0sync_qgis_plugin.ps1" %*
