# 游戏图集

统一使用 32×32、RGB565 小端、64 字节行距，每帧 2048 字节，透明键为 0。不透明黑色用近黑 1，避免被 Color Key 丢弃。`manifest.json` 记录索引、格式、压缩大小和源图校验值。

| 索引 | 内容 |
|---|---|
| 0～15 | 用户人物，`direction*4+walk_frame`；方向下、左、右、上 |
| 16～18 | Kenney CC0 史莱姆、骷髅、蝙蝠 |
| 19～21 | 代码生成的宝石、魔法弹、环绕法球 |
| 22 | 备用魔法闪光 |
| 23 | 红色爱心（骷髅、精英守卫稀有掉落；来自用户提供的图片） |
| 24 | 蓝色精英守卫 |

`game.rgb565` 是 51200 字节的未压缩图集；`atlas_preview.png` 是最近邻放大预览；`software/game_assets.h` 是共享调色板 RLE；`sim/game_expected.hex` 是未压缩像素参考。治疗爱心的灰色画布在生成阶段以边界连通填充识别并转换为 Color Key 透明像素，心形内部深色轮廓会保留。固件启动时解压到 DDR `0x01204000`，游戏通过帧地址选择朝向和动画。

生成命令：执行 `tools/prepare_game_assets.py`，再执行 `tools/build.py firmware`。该脚本复用已核对的前 23 帧 RGB565，将 `source/healing_heart.png` 裁切缩放为红色爱心治疗道具，并追加骷髅改色的精英守卫；随后打包 RLE、参考像素与 PNG，使用 Python 标准库即可。普通编译使用已经生成的文件，不需要联网。

Kenney 原图和许可证在 `source`，GitHub 固定提交及裁切坐标见 [THIRD_PARTY.md](../../THIRD_PARTY.md)。人物和红色爱心来自用户附件。不要将用户素材许可混同为开源敌人素材的 CC0。
