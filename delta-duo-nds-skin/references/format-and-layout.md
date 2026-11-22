# Delta ZIP / NDS 皮肤格式与布局参考

> 依据 Delta 官方 NDS 模板、DeltaCore 源码及本次皮肤制作实践整理。
> 本文记录格式与可复核事实；未在实机验证的行为不写成“已实测”。

## 1. ZIP 与 `info.json`

- `.deltaskin` 是 ZIP；根目录必须有 `info.json`，并放置被引用的 PNG 资源。
- `info.json` 至少应包含 `name`、`identifier`、`gameTypeIdentifier`、`representations`；调试时可显式写 `debug: false`。
- NDS 的官方类型值是：`gameTypeIdentifier: "com.rileytestut.delta.game.ds"`。
- `representations.iphone` 下按显示特性分组：`standard`、`edgeToEdge`、`splitView`、`inner`、`outer`、`cover`；每组再按 `portrait` / `landscape`（`cover` 官方示例为 landscape）。
- 每个方向通常含 `assets`、`items`、`screens`、`mappingSize`；资源键可用 `large`。资源文件名必须与键值完全一致。
- 最小结构示例：

```json
{
  "name": "Example NDS Skin",
  "identifier": "com.example.nds.skin.v1",
  "gameTypeIdentifier": "com.rileytestut.delta.game.ds",
  "debug": false,
  "representations": {"iphone": {"inner": {"portrait": {
    "assets": {"large": "duo_inner_portrait.png"},
    "items": [], "screens": [],
    "mappingSize": {"width": 669, "height": 951}
  }}}}
}
```

## 2. Duo 特性与标准 NDS 屏幕

- `ControllerSkinTraits.DisplayType` 的 Duo 特性为 `inner`（展开后的主屏）、`outer`（外屏/副屏）、`cover`（合盖后的封面）；源码同时接受 `innie` / `outie` 作为 inner / outer 别名。
- `splitView` 是分屏窗口特性，不等同于 inner/outer；官方 NDS 可用横向映射为 **951×318**。
- 标准 NDS 每个游戏屏幕的 `inputFrame` 是 256×192：上屏通常 `{x:0,y:0,width:256,height:192}`，下屏通常 `{x:0,y:192,width:256,height:192}`。
- 官方 Duo `mappingSize`：
  - `inner` portrait：**669×951**；landscape：**951×669**。
  - `outer` portrait：**466×678**；landscape：**678×466**。
  - `splitView` landscape：**951×318**。
  - `cover` landscape：**678×466**（通常无游戏 `screens`，只提供封面画面）。
- `screens[].outputFrame` 是显示屏在皮肤画布中的矩形；它可以与输入的 256×192 不同尺寸，但应保持 4:3，位置和上下屏顺序须与 `inputFrame` 对应。
- `screens[].placement` 可为 `app` 或 `controller`：splitView 官方示例把上屏留给 app，把下屏放进 controller；对应 controller 屏幕才需要皮肤 PNG 的开孔。

## 3. 精确触控与按钮值

- 触控屏项目不是普通按钮：`inputs` 使用对象 `{ "x": "touchScreenX", "y": "touchScreenY" }`，`frame` 覆盖触屏输出区域。
- 精确触控的参考写法是让该 `frame` 与下屏 `outputFrame` 完全一致，并把 `extendedEdges` 设为 0；不要用 `inputs: ["touchScreenX"]` 之类自定义值。
- 按钮值使用 Delta 约定的小写字符串：`up`、`down`、`left`、`right`、`a`、`b`、`x`、`y`、`l`、`r`、`start`、`select`、`menu`。
- 十字键可用对象一次声明四方向：`{"up":"up","down":"down","left":"left","right":"right"}`；面键、肩键、系统键通常用单元素数组，例如 `{"inputs":["a"]}`。
- `items[].frame` 是设计坐标中的命中框；`extendedEdges` 按 top/bottom/left/right 扩大命中区域，不改变 PNG 外观。
- 扩展命中框继承规则：项目自己的 `extendedEdges` 逐边覆盖代表级默认值；未提供的边继续继承默认值。源码随后将 frame 原点向外扩、宽高按左右/上下相加。
- 因此不要仅按可见按钮边缘猜 hitbox；应明确写出需要扩展的边，并检查相邻按钮是否重叠。

## 4. PNG scale 与渲染层

- Duo 的 `large` 资源由 DeltaCore 按 **scale 3.0** 加载（inner、outer、splitView、cover 均如此）；PNG 像素尺寸应是 mapping 坐标的 3 倍，或至少与实际资源约定一致。
- 示例生成器使用 `output_width = mappingSize.width * 3`、`output_height = mappingSize.height * 3` 生成 PNG，并按输出屏幕坐标乘 3 合成纹路。
- 皮肤 PNG 是覆盖层：制作者须主动在 `screens.outputFrame` 对应的位置画透明孔，让游戏画面显示出来；不要假定 Delta 会替不透明 PNG 自动开孔。屏幕边框、按钮、装饰可绘制，游戏画面不要烘焙进交付 PNG。
- 特别注意：肤料内的半透明纹路（例如 `add_pattern.py` 的环线/星形线稿）是叠加在游戏画面上的装饰，不是真正的背景，也不应在预览图中宣称是皮肤内置背景。
- 预览脚本中的紫色或像素画仅是占位游戏画面；它不是交付皮肤的一部分，也不是实机效果证明。
- 渲染层叠顺序建议：先由 Delta 绘制游戏屏幕，再显示皮肤 PNG 的非透明区域；若要让纹路覆盖游戏画面，纹路必须位于透明屏孔区域内、保持 alpha 半透明，并避免用不透明底色封死开孔。

## 5. 构建、版本核验与调试

- 生成 ZIP 前校验：ZIP 根目录、`info.json` 可解析、每个 `assets` 文件存在、`gameTypeIdentifier` 正确、`mappingSize` 与 `outputFrame` 数字有效、所有引用 PNG 可解码。
- 版本核验应以当前 DeltaCore 源码和目标 Delta 版本为准；旧博客、旧示例或不同版本的字段不能直接当作现行规范。尤其要复核 `DisplayType`、资源 scale、splitView placement 和 `extendedEdges` 语义。
- 建议在构建脚本中加入启动前断言（assert）：`info.json` 存在；类型值等于 `com.rileytestut.delta.game.ds`；每个 NDS `inputFrame` 为 256×192；Duo mappingSize 属于上述官方尺寸；触控 item 的 x/y 值正确；PNG 与资源键一一对应。
- 启动调试顺序：先只保留 `inner/portrait` 和一张透明开孔 PNG；确认能载入后，再逐项加入 landscape、outer、splitView、cover、纹路和扩展 hitbox。
- 若黑屏或画面被遮住，优先检查 `screens` 是否缺失/坐标错误、PNG 是否在开孔处 alpha 为 0、`placement: app` 是否被误清除，以及资源是否按 scale 3 生成。
- 若触控偏移，检查 `mappingSize`、`outputFrame`、触控 `frame` 是否使用同一坐标系，再检查 `extendedEdges` 继承造成的扩大范围；不要先改按钮视觉位置。
- `debug` 字段不等于实机诊断开关；除非目标 Delta 版本明确支持，否则应依靠构建断言、ZIP/JSON 检查和运行日志调试。
- 本地脚本生成了 ZIP 或预览，不代表已在 Delta 实机/模拟器安装验证；交付说明应如实标注验证范围。

## 6. 官方源码与文档链接

- DeltaCore 仓库：https://github.com/rileytestut/DeltaCore
- 皮肤主实现（ZIP、资源、scale、screen/item 解析）：https://github.com/rileytestut/DeltaCore/blob/master/DeltaCore/Model/ControllerSkin.swift
- 皮肤特性枚举（standard/edgeToEdge/splitView/inner/outer/cover）：https://github.com/rileytestut/DeltaCore/blob/master/DeltaCore/Model/ControllerSkinTraits.swift
- 官方仓库文档入口（应结合目标版本核验）：https://github.com/rileytestut/DeltaCore/wiki
- Delta 官方 NDS 皮肤模板：https://media.githubusercontent.com/media/rileytestut/MelonDSDeltaCore/master/MelonDSDeltaCore/Controller%20Skin/Standard.deltaskin
