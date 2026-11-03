# W1外围墙体（当前无地砖）

当前按用户要求移除F1A三环及十字地砖，仅编译W1的8个32×32方向/转角模块。原F1A图片、历史floor*.png及提示词保留回退，不参与当前构建或绘制。

prepare_dungeon_assets.py从W1原图确定性裁切/最近邻缩放，生成RGB565与RLE。dungeon_map.h定义四条不重复的墙边，dungeon_view.h在启动时合成424KiB缓存（0x01240000..0x012a9fff）；内部不分配整张世界背景。game_view.h用纯色脏区清理并复制可见墙条。

中心祭坛另由prepare_scenery_assets.py编译为128×128，使用原E1素材，保留透明键、裁剪和可见性判断。详细资源和验证见reports/altar128_walls_20261031.md。
