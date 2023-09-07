本插件提供了解析 gamedata 并实现了 `ArknightsGameData` 以及 `ArknightsGameDataResource` 的方法。

如果你需要使用依赖了这两个类的插件，那么本插件必须安装。

- 超级管理员发送 `更新资源` 可检查资源更新
- 超级管理员发送 `解析资源` 可重新执行解析

## 资源目录

```
Amiya-Bot
└── resource
    └── gamedata
        ├── avatar             干员头像
        ├── building_skill     基建技能图标
        ├── enemy              敌方单位图片
        ├── gamedata           游戏数据
        ├── item               物品图片
        ├── map                地图预览图
        ├── portrait           干员半身照
        ├── skill              干员技能
        ├── skin               已保存的干员立绘
        └── indexes
            └── skinUrls.json  干员立绘 URL map
```

## 获取立绘图片

`resource/gamedata/skin` 文件夹储存的是使用过的干员立绘，若某个立绘从未被使用，目录内将无法找到。

获取干员立绘时，应使用 `ArknightsGameDataResource.get_skin_file` 方法获取，会根据配置的质量下载立绘并返回立绘文件路径。

```python
from core.resource.arknightsGameData import ArknightsGameDataResource

skin_id = 'char_002_amiya#1'
file_path = await ArknightsGameDataResource.get_skin_file({'skin_id': skin_id})
```
