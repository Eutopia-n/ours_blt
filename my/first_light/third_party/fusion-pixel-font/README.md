# Fusion Pixel Font

- 上游项目：[TakWolf/fusion-pixel-font](https://github.com/TakWolf/fusion-pixel-font)
- 版本：`2026.10.25`，简体中文等宽 BDF 字体 `fusion-pixel-12px-monospaced-zh_hans.bdf`
- 上游发布包：`fusion-pixel-font-12px-monospaced-bdf-v2026.10.25.zip`
- 发布包 SHA-256：`d204894d684a0a9c016d6a0fb959184e4f3bd4e728917f37aabc256a8de63e61`
- 字体许可：SIL Open Font License 1.1，文本见本目录的 [OFL.txt](OFL.txt)

固件只嵌入界面使用的 193 个简体中文像素字形，转换为 12×12 点阵并放入 14×14 字符单元；完整上游字体没有打包进工程。要重新生成 `software/font_cn.h`，可在 PowerShell 中运行：

```powershell
$zip = "$env:TEMP\fusion-pixel-font-12px-monospaced-bdf-v2026.10.25.zip"
$fontDir = "$env:TEMP\fusion-pixel-font-12px-monospaced-bdf-v2026.10.25"
Invoke-WebRequest -Uri "https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.10.25/fusion-pixel-font-12px-monospaced-bdf-v2026.10.25.zip" -OutFile $zip
Expand-Archive -LiteralPath $zip -DestinationPath $fontDir -Force
python tools/import_fusion_font.py --bdf "$fontDir\fusion-pixel-12px-monospaced-zh_hans.bdf"
python tools/export_font.py
```
