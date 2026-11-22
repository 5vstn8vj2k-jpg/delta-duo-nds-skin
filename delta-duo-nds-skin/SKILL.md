---
name: delta-duo-nds-skin
description: 为 iPhone Duo 的 Delta 模拟器制作、修改、测试和交付 NDS .deltaskin 皮肤。用于定制双屏布局、竖屏或横屏、大主屏与小副屏、配色主题、按钮材质、触控屏透明叠加图案、预览和导入排错；不限于凯西或宝可梦主题。
---

# iPhone Duo · Delta NDS 皮肤

交付真正可导入的 `.deltaskin`，而不仅是效果图；沿用用户指定的主题、设备模式和已有版本，避免把凯西风格当成唯一选择。制作前读取 [格式与布局参考](references/format-and-layout.md)。核对用户所用 Delta 的当前兼容性与官方格式，特别是在设备型号、程序版本或模板变更时；不能联网时说明参考版本可能过时，不假称最新。

## 工作流程

1. **确定范围。** 从用户描述或已有皮肤确定主题、配色、按钮/边框质感、内屏/外屏、竖屏/横屏、上下屏大小和位置，以及是否要触控屏图案。已有皮肤的修改优先只改明确要求的部分，其余模式、控制、视觉和交互尽量保留。信息不足时采用已有布局或官方模板的合理默认值，告知假设；仅在缺少关键文件或偏好决定无法继续时提问。
2. **取得基准。** 用户提供的皮肤优先，工作于副本；否则从 [Delta 官方 NDS 示例](https://media.githubusercontent.com/media/rileytestut/MelonDSDeltaCore/master/MelonDSDeltaCore/Controller%20Skin/Standard.deltaskin) 获取模板，以其 `info.json` 为基准。不要复用未获许可的第三方素材；可以生成原创图形。按需参阅 [官方格式](https://github.com/altstoreio/Delta-Docs/blob/master/skins/README.md)。不要把上一任务的本地路径视作本技能的资源。
3. **设计与映射一起迭代。** 用矢量或精准图像工具分别绘制各 representation 的背景、按钮及边框，生成与画布对应的 PNG；先算屏幕与控件坐标，再从同一组坐标画图，确保视觉位置和触控位置对齐。调整某个屏幕后，同步更新显示输出框、遮罩、屏幕触控项及扩展边缘。遵循原始模板的有效 NDS 输入与模式结构；通常应覆盖内外屏的横竖屏，按模板保留 splitView/cover 或明确说明缺失模式。对布局或素材作增量修改时，保留旧版文件并使用新标识符。
4. **处理游戏屏幕。** 不在画面区域填充不透明皮肤：上屏和下屏需要透明开窗，让实际游戏显示。若用户要屏幕上的花纹，只在用户同意或明确要求时使用低透明度前景叠加，不把它描述成可见的游戏背景；可以提供不叠加的版本。保持 4:3 避免拉伸，除非用户另有要求。增大主屏可能跨越展开内屏的折痕；明确提示并优先保证控制不遮挡画面。示例参考中的屏幕图像只是预览占位，不得写进皮肤冒充游戏。
5. **打包与验证。** 将 `info.json` 和所有引用的 PNG 放在 ZIP 根目录，扩展名用 `.deltaskin`，赋予非冲突的 identifier。运行本技能的校验器，逐项修复错误；审视屏幕透明度、叠加程度、按钮可辨性、真实有效热区和 4:3 比例，检查预览及压缩包内容。校验器的警告需人工判断，静态通过不等于 Delta 实机验证。切勿以示意预览或程序检测冒充真机运行结果。
6. **交付。** 提供 `.deltaskin` 和关键模式的预览图，说明支持的设备形态/方向、主副屏比例、可能跨折痕、透明前景叠加，以及真机测试状态。安装方法：在 iPhone 上打开 `.deltaskin` 并选择在 Delta 中导入，再在 Delta 对应系统的控制器皮肤设置中选择；如界面不同，参考 [Delta 导入说明](https://faq.deltaemulator.com/using-delta/controller-skins)。遇到掉帧时，先与默认皮肤在相同游戏场景比较，再排查低电量、散热、快进和滤镜等；不要未经对照就断言皮肤导致性能问题。

## 自带工具

以下的 `$SKILL_DIR` 指本技能目录；执行前将其设为实际安装路径。用新的输出目录，避免覆盖已有文件。

- `scripts/validate_deltaskin.py`：用 Python 和 Pillow 对归档、NDS 元数据、资源、画布、显示框与触控关系做静态检查。例如：

  ```bash
  python3 "$SKILL_DIR/scripts/validate_deltaskin.py" /path/to/skin.deltaskin
  ```

  校验器不能验证每个 Delta 版本、屏幕渲染顺序、观感或真实设备操作；还须人工查看预览并如实说明实测情况。
- `scripts/build_crystal_example.py`：根据外部官方 NDS 模板生成本次凯西灵感水晶材质的**示例**，支持官方或放大主屏布局及可选超能力前景图案；不将这种风格强加于其他主题。它需要 Python、Pillow、CairoSVG，使用 `--help` 查看参数。不同主题或其他布局应将脚本复制到工作目录再改配色、图案及几何，或另行设计，不要在技能安装目录直接改写脚本。模板中仅使用元数据，重新绘制 PNG；以用户皮肤为基准进行小幅修改时应另写保留原素材的增量脚本，而不是直接用示例覆盖。

  ```bash
  python3 "$SKILL_DIR/scripts/build_crystal_example.py" \
    --template /path/to/official-nds.deltaskin --output-dir /path/to/new-output \
    --name 'Crystal Example' --identifier com.example.nds.crystal.v1 \
    --layout big-main --overlay psychic
  ```

用真实输入跑生成/修改脚本，验证最终包和预览；若需要其他风格的 AI 图像，遵守当前环境的图像生成技能与素材权限要求，依然用程序精确开窗和生成热区。
