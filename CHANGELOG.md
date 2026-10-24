# Changelog

记录会影响使用方式的更新。条目按本仓库完成同步的日期排列，说明新入口、所需输入、预期结果和迁移方法；仅有措辞调整的更新不逐文件展开。

## 2026-10-24：接入 Pi 的 REA MCP

创建 Pi 用户级 `~/.pi/agent/mcp.json` 的 REA stdio 注册，保留已有共享 skill 链接。README 补充新机器的安装命令和 Pi 的连接检查方式。已有会话使用 `/reload` 加载，再通过 `/mcp` 查看状态。

## 2026-10-24：接入 OMP 的 REA MCP

为 OMP 默认 profile 创建 `~/.omp/agent/mcp.json` 的 REA stdio 注册，并在 `~/.omp/agent/skills/reverse-engineer-anything` 建立指向本仓库的软链接。其余客户端的注册保持原样；OMP 链接单独维护，未扩大批量 skill 分发范围。多机配置命令补入 README。重启 OMP 后，新会话才能加载此次接入。

## 2026-10-24：安装 REA 6.7.0 与共享 skill

新增 `morluto/rea` 的 `reverse-engineer-anything`，固定至 6.7.0 发布提交 `27dc42d10249f0410904a75c0997842eb03b931c`，共 7 个文件；当前清单为 7 个来源、58 个 skill。Claude / Codex / Pi 共用仓库内实体文件和各自软链接。

本机已全局安装 `rea-agents@6.7.0`，为 Codex、Claude Code 注册 MCP；配置文件留有备份，结构比对确认其他配置未改。安装使用 `--skill=false`，避免覆盖仓库管理的软链接。Pi 仅共享 skill，尚未注册 REA MCP。

验证：`rea doctor --client codex --client claude_code --json` 的指定范围通过；`rea mcp doctor --json` 完成真实 stdio 握手、列出 207 个工具及 6 个提示，并通过 `binary_session` 请求。独立 JavaScript 样例生成了分析 Evidence。尚需重启客户端，确认新会话加载工具；原生反编译引擎未安装，此次验证不代表原生或 Android 分析已可用。

其他机器需另装同版本 npm 包并执行本机 MCP setup；命令、输入与预期输出见 [README 的 REA 安装说明](README.md#rea每台机器单独安装运行时与-mcp)。skill 原样保留 GitHub 发布源码，npm 内置版仅增加工具数及示例版本替换；升级时需同时核对 CLI 与固定提交。

## 2026-10-24：移除 Herdr skill

按用户选择移除 `herdr` skill、`herdrdev/herdr` 同步来源、本机安装器中的对应记录，以及 Claude / Codex / Pi 的软链接。现有清单为 6 个来源、57 个受管 skill；Herdr 应用本身不作变更。移除前的文件保留本机恢复副本。

其他机器拉取变更后运行 `python3 scripts/sync-skills.py --link` 清理旧链接。来源登记已移除，后续同步不会自动重新安装此 skill。

## 2026-10-24：移除钉钉技能包及四个本地维护技能

按用户选择移除全部 16 个 `dingtalk-*` 技能，以及 `accept-issue`、`humanizer-zh`、`implement-codex`、`land-issue`，总数由 78 个降为 58 个。同步清除 `upstream.json` 中的本地维护登记、Codex 对 `implement-codex` 的排除项和三端对应软链接。旧文件与链接保留在本机恢复目录，不随 Git 分发。

这些入口不再由本仓库提供。其他机器拉取本次变更后，执行 `python3 scripts/sync-skills.py --link` 清理对应旧链接；该命令无需网络或新增依赖。清单已移除这些登记，后续按当前配置同步上游不会重新安装它们。此前 changelog 中有关钉钉入口的用法仅作为历史记录。

Matt Pocock 的 27 个技能保持不变，已逐文件比对内容与可执行权限，均与作者上游 `main` 的 [5beb35b](https://github.com/mattpocock/skills/commit/5beb35b040e3de97e54fa9e386d7e42d15c295c2) 一致，engineering / productivity 范围没有缺失项。

## 2026-10-24：Kami 手机按钮改用自然宽度，补充页面设计规则

同步中文、英文、韩文官网模板和设计说明，共 4 个文件，对齐上游 [44bf3a4](https://github.com/tw93/kami/commit/44bf3a4b8aa1d213297ed12defd6407b8679da6e)，版本号仍为 `1.18.0`。按钮变化来自 [d021681](https://github.com/tw93/kami/commit/d02168186e9c2028d5116b8f38611797134746c5)，设计规则来自 [4b55540](https://github.com/tw93/kami/commit/4b55540fe45df06f83aabdde9a2fc8ed2d620dd6)。

手机首屏按钮现在保持文字加两侧留白的自然宽度，左对齐，放不下时第二个按钮换行。`max-width: 480px` 下两类按钮的内边距改为上下 10px、左右 24px，首屏按钮改用 `flex: 0 0 auto`，不再分摊整行剩余空间。此规则替换 10 月 21 日记录中的拉伸布局；桌面样式继续沿用。

### 更新后的用法

提供现有 HTML、产品文案及各语言按钮标签，在 Codex 中发送：

```text
$kami 按最新官网规范更新这个页面：手机首屏按钮使用自然宽度，左对齐，放不下时换行；保留至少 44px 的触控高度。删去与标题重复的上眉文字，整理字号和嵌套圆角。在 320px 和 375px 下检查最长语言，并核对桌面布局，交付更新后的 HTML 和引用资源。
```

Claude Code 用 `/kami`，Pi 用 `/skill:kami`。没有新增运行依赖，使用现有 HTML/CSS 和浏览器即可验收；字体、图片及下载和购买地址仍由页面内容决定。生成页面的价格卡购买链接继续按 10 月 21 日的说明单独填入。

### 迁移已有页面

已采用上一版布局的页面，在现有手机媒体查询中把按钮的 `padding: 13px 16px` 改为 `10px 24px`，把首屏按钮的 `flex: 1 1 auto` 改为 `0 0 auto`。保留容器的 `flex-wrap: wrap`、8px 间隔和按钮的 `white-space: nowrap`；移除额外的整行拉伸或等宽覆盖规则。换行不会缩短单个标签，仍需用最终字体和实际最长文案检查是否超出可用宽度。

新版设计说明还要求：上眉文字应补充标题没有的信息；屏幕页面以显示、标题、正文、次级四档字号为目标，次级文字至少 12px；嵌套圆角按外圆角减去内缩距离计算；按钮优先用填色表达层级，边框用于划分区域。迁移时按内容角色调整，不把屏幕字号规则套到印刷文档。

Matt 的 engineering、productivity 仍与 [5beb35b](https://github.com/mattpocock/skills/commit/5beb35b040e3de97e54fa9e386d7e42d15c295c2) 一致。7 个来源、58 个受管技能和 20 个本地技能的归属不变，`upstream.json` 无需调整；本轮没有新增、改名或弃用入口。

验证：47 项维护脚本测试、49 个模板及 Mermaid 的 token 检查通过。中英韩模板在 320、375、480、481、1024px，以及德文长标签和中文短标签下完成 36 组更新前后对比；按钮没有溢出，手机触控高度为 45.25 至 45.69px，桌面尺寸未变。浏览器测试阻断外部请求，使用系统回退字体；交付具体页面时仍需用最终字体复查。Codex 77、Claude 78、Pi 78 个链接均有效，Pi 原生加载器读取全部 78 个技能且无诊断。

## 2026-10-21：Kami 调整官网按钮层级和手机布局

同步 Kami 中文、英文、韩文官网模板及设计说明，共 4 个文件。上游提交为 [6b399e9](https://github.com/tw93/kami/commit/6b399e93a5dfce0eaa7e3aabcc04cc260f01b8f6)，版本号仍为 `1.18.0`。

次按钮 `.btn-ghost` 现在使用象牙白底、近黑文字和 `--line` 细边框，悬停时改为暖沙色；主按钮保留产品主色，两种按钮的边框都改为 1px。手机上两个首屏按钮按文字长度分配宽度，间隔 8px；放不下时换成两行，按钮文字保持单行。

### 更新后的用法

准备产品名、主色、支持平台、下载地址和购买地址，再在 Codex 中发送：

```text
$kami 为 Example 制作支持免费试用的付费应用官网。首屏用实心下载按钮和浅底购买按钮，价格卡保留实心购买按钮。使用新版手机布局，在 320px 和 375px 下检查最长语言的按钮文字与链接，交付可部署的 HTML 及引用资源。
```

Claude Code 用 `/kami`，Pi 用 `/skill:kami`。没有新增运行依赖；模板使用 CSS Flexbox，需要浏览器验收。预期产物是填好文案、下载与购买链接的官网 HTML，以及页面引用的字体和图片。按钮文案用动作加对象，例如 `Download for Mac`、`Buy Example`，购买按钮不附价格。

### 迁移已有页面

在页面副本中迁移 `.btn-primary`、`.btn-ghost` 及其悬停样式，并同步 `max-width: 480px` 下的 `.hero-cta` 规则：容器启用 `flex-wrap: wrap`，按钮使用 `flex: 1 1 auto` 和 `white-space: nowrap`。移除旧的 `max-width: 360px` 强制竖排规则，避免它覆盖新布局；不要用 `flex: 1 1 0` 强制等宽。以实际最长文案在 320px 和 375px 下验收，确认文字不溢出且点击目标正确。

现有模板的价格卡仍复用 `CTA_PRIMARY_URL` 和 `CTA_PRIMARY_LABEL`。首屏主按钮设为下载时，生成的页面必须把价格卡按钮单独填为购买文案和购买地址，不能仅全局替换这两个占位符。原有网站需自行应用这些修改，本次维护只更新技能仓库。

Matt 最新提交为 [5beb35b](https://github.com/mattpocock/skills/commit/5beb35b040e3de97e54fa9e386d7e42d15c295c2)，变化位于未纳管的 `in-progress/chief-of-staff`；engineering、productivity 的 27 个技能没有变化。7 个来源、58 个受管技能和 20 个本地技能的归属不变，`upstream.json` 无需调整；没有新增、改名或弃用入口。

### 验证记录

7 个上游复查一致，Kami 全部 118 个文件及可执行模式与指定提交相同，其余 77 个技能连同原有缓存均保持不变。47 项同步测试通过，Pi 加载 78 个技能且无诊断；Codex、Claude、Pi 的 77、78、78 个仓库链接正确，递归扫描无断链。Kami 的颜色检查覆盖 49 个模板及 Mermaid 主题。

浏览器以相同输入对比新旧模板，共执行 24 个场景，其中 12 个为新版：覆盖三种语言的 320px、375px、1024px 布局，以及德文长按钮和中文短按钮。新版按钮均未溢出，短文案可并排，较长文案会换行；已查看中文、韩文和德文样例截图。测试阻止了外网请求，使用系统回退字体，尚未验证产品最终字体、实际下载和付款流程，也未发布网站。

## 2026-10-19：read 增加可选 DeepSeek，Kami 更新官网配色和字体规则

本次同步 `read` 的 4 个文件和 `kami` 的 7 个文件。Matt 的 engineering、productivity 仍为 27 个技能，没有新增、改名或弃用；受管来源仍为 7 个仓库、58 个技能，另保留 20 个本地技能，来源清单无需调整。

### read：按需启用 DeepSeek 搜索与网页提取

新增 `scripts/deepseek.py`，使用 Python 3 标准库。先在运行环境中配置 `DEEPSEEK_API_KEY`，再使用以下命令；查询词或 URL 会发送给 DeepSeek，可能产生 API 费用，因此仅用于已同意发送的公开内容。

```bash
READ_SCRIPT_DIR="$HOME/.agents/skills/read/scripts"
python3 "$READ_SCRIPT_DIR/deepseek.py" search "site:python.org asyncio" --count 5
```

`search` 接受 1 至 128 个字符的查询，返回带 URL、站点、日期和评分的编号结果；加 `--content` 请求正文，加 `--json` 保留原始响应。摘要可能是索引时的快照，引用事实前仍需读取原页。`fetch` 输出来源 URL 和提取的正文。未设置密钥时返回退出码 2，不发送请求；HTTP 或网络失败返回 1。

直接调用 `deepseek.py fetch` 时，空正文也可能记录 `status=ok` 并返回 0，因此自动化流程必须额外检查正文。以下示例请求 JSON，只在 `content` 是非空字符串时输出正文；JSON 格式错误或空正文都会使整条命令失败。服务端响应字段类型异常时，helper 还可能直接抛出异常，不能假定每次失败都有结构化日志。

```bash
set -o pipefail
python3 "$READ_SCRIPT_DIR/deepseek.py" fetch "https://docs.python.org/3/library/asyncio.html" --json |
  python3 -c '
import json, sys
data = json.load(sys.stdin)
body = data.get("content") if isinstance(data, dict) else None
if not isinstance(body, str) or not body.strip():
    sys.exit("DeepSeek did not return a non-empty body")
print(body.strip())
'
```

`fetch.sh URL` 继续只从源站抓取并在本地提取。显式选择 `--use-proxy` 后，本地提取失败且存在密钥时，会先试 DeepSeek，再尝试原有的 defuddle 和 Jina。以前使用该选项的环境若已经设置密钥，现在会增加这个调用；只想沿用原有第三方提取顺序时，可仅在这条命令中移除密钥：

```bash
env -u DEEPSEEK_API_KEY bash "$READ_SCRIPT_DIR/fetch.sh" --use-proxy "https://example.com/"
```

在 Codex 中可说 `$read 使用 DeepSeek 搜索公开的 Python asyncio 官方资料，先列来源，再读取与当前问题有关的页面`。Claude Code 用 `/read`，Pi 用 `/skill:read`。此更新不自动配置密钥，也不授权把内部或需登录的链接发送给第三方。完整命令见 [读取方法](skills/read/references/read-methods.md)。

### Kami：官网采用产品主色，按渲染场景选择字体

Kami 版本号仍为 `1.18.0`。新版官网流程优先从产品图标、界面或品牌素材中确定主色；缺少明确主色时展示候选色让用户选择，无偏好时才保留墨蓝。迁移已有官网时一起调整 `--brand`、`--brand-light`、`--brand-tint`，保留暖色背景和灰阶，并检查正文链接及按钮文字的 4.5:1 对比度。新增 `--line: #d8d5c8` 用于屏幕界面的细边框，字号使用统一档位，垂直间距按 4 的倍数整理。

中文 PDF 和内嵌 SVG 继续优先放中文字体；自托管、且用 `unicode-range` 限定中文字符范围的网站，则按新版规则把西文字体放在中文子集之前。商业产品官网按新版要求将模板默认的 TsangerJinKai02 换成 Source Han Serif，并自托管 WOFF2 子集。子集应覆盖正文及会显示在页面上的属性文字，文案变化后重新生成并核对缺字。

准备可用于网站的源字体 `Source.otf`、包含全部所需字符的 `chars.txt`，并确保 FontTools 的 `pyftsubset` 支持 WOFF2，然后执行：

```bash
pyftsubset Source.otf --text-file=chars.txt --flavor=woff2 --output-file=serif-sc-regular.woff2
```

在 Codex 中可说 `$kami 按现有产品主色制作中文商业产品官网，检查品牌色对比度，使用 Source Han Serif 的自托管中文子集，交付可部署的 HTML 和字体资源`。Claude Code 用 `/kami`，Pi 用 `/skill:kami`。这里只同步模板和规则，没有改动任何现有网站或安装字体。完整迁移规则见 [官网设计说明](skills/kami/references/design.md)。

### 上游版本

| 上游 | 本次核对的提交 | 变化 |
|---|---|---|
| mattpocock/skills | [49dd158](https://github.com/mattpocock/skills/commit/49dd158d1076134a641b33efb035946536778336) | 无变化 |
| tw93/Waza | [840f926](https://github.com/tw93/Waza/commit/840f926af48c98e0b36a3a64658a9ddc4cf7e716) | `read` 新增可选 DeepSeek 搜索和提取 |
| tw93/kami | [0b94336](https://github.com/tw93/kami/commit/0b9433633616318349d3da87c06e690a4d8f5b25) | 官网配色、字号和字体规则 |

### 验证记录

7 个上游再次比对通过，更新内容与表中提交的文件和可执行模式一致；其余 76 个技能及原有运行缓存均保留，来源清单没有变化。Codex、Claude、Pi 的 77、78、78 个仓库链接均有效，包含隐藏目录的扫描没有断链，已清理的旧入口没有重新出现。

从暂存 Git 树导出的隔离安装通过 47 项同步测试，三端链接安装完整，Kami 的颜色检查覆盖 49 个模板及 Mermaid 主题。当前安装和隔离安装均由 Pi 加载全部 78 个技能，没有缺失、重复或诊断信息；新增 Python、修改后的 Shell 和 JSON 通过语法检查。

DeepSeek 离线测试覆盖缺密钥、无效查询、正常搜索和提取、HTTP 与网络失败；模拟回退链确认默认模式不调用第三方，显式代理每轮最多调用一次 DeepSeek。文档中的正文校验示例通过有效正文和各类空值、异常类型、无效 JSON 的正反例，`pipefail` 能保留上游命令的失败状态。此次没有请求真实 DeepSeek 服务，没有生成网站、字体子集或 PDF，在线 API 可用性及实际页面渲染未据此验证。

## 2026-10-16：启用每日维护，纳管 Cloudflare，Kami 升至 1.18.0

本次同步 `check`、`health`、`herdr`、`kami` 的 43 个文件，并将本机已有的 19 个 Cloudflare 官方技能纳入 `upstream.json`。现在共维护 7 个上游、58 个受管技能，另保留 20 个自建或手工维护技能。Matt 仍为 27 个，本次没有变化，也没有新增弃用项需要移除。

### 每日检查后提交和推送

Codex 已设置每天 09:00（Asia/Taipei）在本机执行维护：先同步远端和检查本地编辑，再核对上游更新及弃用关系，维护 Codex、Claude、Pi 的链接，更新说明并验证，最后提交维护改动并推送到 `origin/main`。没有变化时不创建空提交；有更新、失败或需要处理的问题时通知。

该任务保存在本机 Codex，克隆 Git 仓库不会复制定时设置。手工执行相同的更新阶段可用：

```bash
cd "$HOME/.agents"
python3 -B scripts/sync-skills.py
# 核实报告中的删除、改名、拆分，以及本地编辑后再应用
python3 -B scripts/sync-skills.py --apply --prune
python3 -B -m unittest discover -s tests -q
```

只读检查发现更新时返回 1 是正常报告。`--apply --prune` 遇到未提交的技能改动会拒绝覆盖，应先检查归属和差异；不要通过强制重置或删除本地文件让检查通过。较大变化的用法和迁移说明补齐后，再提交本轮维护文件并推送。

### Cloudflare：19 个已有技能开始随仓库维护

纳管前已逐文件确认本地内容和可执行模式与官方上游一致；这次补齐了三端共 57 个软链接。`.skill-lock.json` 保留作本机安装记录并加入 Git 忽略，后续来源、更新和裁剪以 `upstream.json` 为准。

按实际任务选择入口，例如在 Codex 聊天中发送：

```text
$cloudflare 根据这个应用的需求选择 Cloudflare 产品，并说明存储、计算和部署方式。
$cf-cli 查找完成当前资源查询所需的命令，核对参数和目标账号后执行只读查询。
$workers-best-practices 审查当前 Worker 的绑定、错误处理和生产配置。
```

Claude Code 使用 `/cloudflare` 等对应名称，Pi 使用 `/skill:cloudflare`。已有 `wrangler.jsonc`、`wrangler.json` 或 `wrangler.toml`、且没有 `cloudflare.config.ts` 的项目继续用 `wrangler`；只有明确要迁移时才运行 `cf migrate`。技能文件同步不会自动安装 `cf` 或 Wrangler，也不会部署资源。

数据分析、日志和框架入口还包括 `basin`、`k2`、`nextjs-on-cloudflare`；后者的新项目流程使用 vinext，维护既有 OpenNext 项目时保留原方案，迁移前先做兼容性检查。完整入口见 [Cloudflare](skills/cloudflare/SKILL.md) 和 [CLI 选择规则](skills/cf-cli/SKILL.md)。

### Kami 1.17.0 → 1.18.0：从数据生成图表

图表现在由 JSON 数据生成 SVG，支持柱状图、折线图、横向条形图、环形图、蜡烛图和瀑布图。以 `chart-spec.json` 为例，下面是演示数据，使用时替换为已确认的真实数据和来源：

```json
{
  "type": "bar",
  "categories": ["第一期", "第二期"],
  "series": [{"name": "完成数", "values": [12, 18]}],
  "unit": "项",
  "source": "演示数据"
}
```

在文档工作目录执行：

```bash
python3 "$HOME/.agents/skills/kami/scripts/build.py" --chart chart-spec.json -o chart.svg
# 将生成的 SVG 放入 filled.html 后，核对图表与内嵌数据是否一致
python3 "$HOME/.agents/skills/kami/scripts/build.py" --check-charts filled.html
python3 "$HOME/.agents/skills/kami/scripts/build.py" --deliver filled.html content.json
```

SVG 内嵌数据规格，后续检查会按规格重建并比较图形与标签。修改数值时编辑 JSON 后重新生成，不要直接拖改柱高或改 SVG 标签。窄栏图表在规格中设置 `"size": "compact"`；不要靠压缩整张 SVG 让文字挤进页面。字段与数量限制见 [图表规格](skills/kami/references/diagrams.md#9-data-charts)。

品牌网站可以生成配置草稿：把下面示例网址换成实际品牌网站，输出保存在指定文件，检查颜色、字体和 logo 候选并接受后再用于文档：

```bash
python3 "$HOME/.agents/skills/kami/scripts/brand_extract.py" https://example.com -o brand-draft.md
```

长文、提案或分析报告需要 Word 协作版时，明确要求同时交付 PDF 和 DOCX。新流程先把内嵌 SVG 转为 PNG，再通过 pandoc 转换，需要 `pandoc` 和 `rsvg-convert`；复杂网格布局不会原样保留。步骤见 [DOCX 交付说明](skills/kami/references/production.md#part-5--html---docx-pandoc--svg-to-png)。PDF 仍需运行 `--deliver` 并逐页检查，视觉修正每轮处理最明显的三个问题，最多三轮后列出残余问题。

### Health 和 Herdr 的使用变化

`health` 在从摘要检查升级到深入检查时，会保留原来的范围。只检查静态配置、不读取会话历史时使用：

```text
$health 只检查当前项目的 agent 指令、skills、hook 和 MCP 配置，深入检查也保持这个范围。
```

Herdr 的 `idle`、`done` 或命令提交成功不保证后台任务已完成，也不保证目标 agent 在前台。控制已有 pane 时应读取近期输出和实际结果；暂停后恢复的 agent 需要重新确认前台状态。这里只更新技能说明，没有操作任何 Herdr 会话。

### 本次上游提交

| 上游 | 提交 |
|---|---|
| mattpocock/skills | [49dd158](https://github.com/mattpocock/skills/commit/49dd158d1076134a641b33efb035946536778336) |
| tw93/Waza | [2585ee0](https://github.com/tw93/Waza/commit/2585ee0f46bcefd9adb1b8f5d4ce19184a4d2929) |
| tw93/kami | [d9352d1](https://github.com/tw93/kami/commit/d9352d1321b24f37b53a6216ecae2543f8dc3a02) |
| microsoft/playwright-cli | [b85c7a7](https://github.com/microsoft/playwright-cli/commit/b85c7a736bb473bf55b584e54a09ffa698d6d871) |
| herdrdev/herdr | [143bf5f](https://github.com/herdrdev/herdr/commit/143bf5fd4781d164260c63fe28e7dc08054ad32f) |
| Agents365-ai/365-skills | [02d9107](https://github.com/Agents365-ai/365-skills/commit/02d91076f86efef61d5c70ed1ab28411899063ac) |
| cloudflare/skills | [86505e4](https://github.com/cloudflare/skills/commit/86505e44f87d801aa1864a3c4109e9a8ae5c409f) |

### 验证记录

同步脚本复查通过，7 个受管上游均无内容或文件模式差异。Codex、Claude、Pi 分别有 77、78、78 个指向本仓库的有效技能软链接，再次执行 `--link` 没有产生改动。Codex 沿用不创建 `implement-codex` 链接的配置；三端扫描包含隐藏恢复目录，没有断链。

从待提交的 Git 树导出到临时目录后，三端链接安装和 47 项同步测试通过；变更中的 86 个 Python 文件及 11 个 Shell 文件通过语法检查。Pi 1.2.0 加载全部 78 个技能，同时读取 Pi 与共享目录时也没有缺失、重复或诊断信息。Kami 的图表生成和数据校验通过，修改图表标签后校验按预期拒绝；品牌提取命令的帮助入口可用。

交付复核覆盖了来源归属与误删、敏感文件入库、安装与文档组合、失败重试和并发修改。未发现需修复的问题。自写文档的空白检查通过；保留了上游或本地保留技能原有的空白格式，未为格式检查改写第三方内容。定时任务已保存并启用，尚未等待首个定时触发；未执行真实 Cloudflare 部署、钉钉在线操作、完整 PDF 渲染或 DOCX 转换。

## 2026-10-13：补齐钉钉技能登记与链接，继续同步上游

重新核对了仓库远端、6 个受管上游和三端软链接。本次更新 `wizard`、`check`、`health`、`write`、`kami`，共 55 个文件，没有新增或移除受管技能。Matt 仍为 27 个技能，这次只有 `wizard/template.sh` 变化。

### 钉钉入口：从 dws 技能改用 dingtalk-*

本次检查前，本地旧 `skills/dws/` 已被替换为 16 个 `dingtalk-*` 目录，Claude 和 Pi 的链接也已存在，但清单仍登记旧入口，Codex 缺少对应链接。这次补齐了登记和 16 个 Codex 链接，保留全部钉钉技能原文，没有重新安装或升级钉钉 CLI。

泛称钉钉操作或需要跨产品编排时使用 `dingtalk-shared`；已明确产品时直接用对应技能。例如在 Codex 聊天中发送：

```text
$dingtalk-shared 我需要查询钉钉里的资料，请先按内容类型选择产品技能。
$dingtalk-calendar 查询今天的日程，按当前会话时区展示。
$dingtalk-doc 读取我提供的钉钉文字文档链接并概括待办项。
```

Claude Code 将 `$dingtalk-calendar` 换成 `/dingtalk-calendar`，Pi 换成 `/skill:dingtalk-calendar`。其他技能同理。旧的 `$dws`、`/dws` 或 `/skill:dws` 技能调用应按任务改成相应入口；终端工具的名称仍是 `dws`。

其他入口包括 `dingtalk-aisearch`、`dingtalk-aitable`、`dingtalk-chat`、`dingtalk-contact`、`dingtalk-drive`、`dingtalk-event`、`dingtalk-mail`、`dingtalk-minutes`、`dingtalk-misc`、`dingtalk-tag`、`dingtalk-todo`、`dingtalk-wiki` 和离线制卡的 `dingtalk-aicard`。产品选择和所需输入见 [共享入口](skills/dingtalk-shared/SKILL.md)。

这些目录在 `upstream.json` 的 `untracked` 中登记，只维护链接并保留本地内容。它们尚未配置 Git 上游，因此「6 个受管上游已同步」不代表钉钉包已经检查到最新版本。

### Matt wizard：迁移现有向导的执行入口

新版模板把所有交互步骤放进 `run_wizard()`，在文件最后调用它，使 Bash 在第一次提示前读完整个函数。生成新向导时继续调用 `wizard`，复用新版 [template.sh](skills/wizard/template.sh)：

```text
$wizard 为当前项目生成 setup-wizard.sh，使用新版模板的 run_wizard 入口，复用已有 .env 配置，并在写入后让后续步骤立即使用新值。
```

迁移以前生成的向导时，保留前面的辅助函数，把 `TOTAL_STAGES`、各个 `stage` 和 `finish` 放入以下结构，再运行语法检查：

```bash
run_wizard() {
  # 在这里放入原有的 TOTAL_STAGES、交互步骤和 finish
  :
}
run_wizard "$@"; exit
```

```bash
bash -n setup-wizard.sh
```

`write_env KEY VALUE` 现在既更新 `.env`，也设置当前 Shell 中的同名变量，后续步骤无需重新读取文件。已有值除了模板自己的单引号格式，也支持不含转义、美元符号或内部双引号的普通双引号格式；复杂值会要求重新输入。终端清屏失败时也有备用处理。

### Kami：交付入口不变，检查失败会明确报告

版本文件仍为 `1.17.0`，本次按提交继续同步了 45 个文件。`--deliver` 现在会捕获检查器异常并输出失败结论，公式检查失败时跳过 PDF 渲染，模板样式检查按识别出的文档类型执行。

在已准备 `filled.html` 和 `content.json` 的文档目录中继续运行：

```bash
python3 "$HOME/.agents/skills/kami/scripts/build.py" --doctor
python3 "$HOME/.agents/skills/kami/scripts/build.py" --deliver filled.html content.json
```

出现 `ERROR` 或 `NOT READY` 时先修复再重跑，不能把目录里原有的 PDF 当作本次成功产物。出现 `READY` 后仍需逐页查看图片。含中文的 Mermaid 图改用中文字体优先的字体链；字体和模板细节也有修正，复用旧 HTML 的文档应重新检查字体、换行和布局。

### Waza：调用名称不变，补充使用边界

- `health` 更准确地区分 MCP 的禁用、待批准和未验证状态，并识别 hook 命令中的环境变量与 Shell 包装。只核对配置时可发 `$health 只检查当前项目的 agent 指令、skills、hook 和 MCP 配置`，静态配置存在不能当作已连接成功。
- `check` 在用户同时授权提交、推送、发布等多个步骤时，会按授权范围合并相应检查；仅授权提交或推送仍不包含公开回复、关闭工单等操作。
- `write` 加强作者原有表达的保留、多语言同步和技术说明消歧。可发 `$write 检查这份指南的前置条件、命令和界面路径，保留作者口吻，并核对其他语言版本是否遗漏条件`；改完还要复核这次修改是否引入新歧义。

### 上游与验证记录

| 上游 | 本次核对的提交 | 技能变化 |
|---|---|---|
| mattpocock/skills | [49dd158](https://github.com/mattpocock/skills/commit/49dd158d1076134a641b33efb035946536778336) | `wizard` 1 个文件 |
| tw93/Waza | [318d6c2](https://github.com/tw93/Waza/commit/318d6c2c219894798b09c2b39d7f83d0be1a313c) | `check`、`health`、`write` 共 9 个文件 |
| tw93/kami | [372a6ca](https://github.com/tw93/kami/commit/372a6ca36600b180370dd975225316bb75db716e) | `kami` 45 个文件 |
| microsoft/playwright-cli | [b85c7a7](https://github.com/microsoft/playwright-cli/commit/b85c7a736bb473bf55b584e54a09ffa698d6d871) | 无变化 |
| herdrdev/herdr | [241b99c](https://github.com/herdrdev/herdr/commit/241b99cd397bb642eaabcfee1647bcecffb26be1) | 受管技能无变化 |
| Agents365-ai/365-skills | [8a927e8](https://github.com/Agents365-ai/365-skills/commit/8a927e8e2cfef2b90c3f78e06cca218572afa36b) | 受管技能无变化 |

更新前先逐文件核对：5 个待更新目录与 10 月 9 日记录的上游版本完全一致。保留完整恢复副本后应用差量补丁，其他 54 个技能的内容和可执行模式均未改变，Git 暂存区与提交也未改变。恢复副本位于 `.sync-skills-recovery/recheck-2026-10-13.*/before/skills/`。

同步脚本再次体检通过，6 个受管上游没有内容或文件模式差异；47 项同步测试通过。Codex、Claude、Pi 分别有 58、59、59 个指向本仓库的技能软链接，包含隐藏恢复目录在内无断链。Codex 按现有配置不创建 `implement-codex` 链接。

重复运行 `--link` 后，176 个链接的目标、inode 和修改时间均未改变。Claude 的 `synced/` 目录另有 13 个外部实体技能，与本仓库技能无同名冲突，原样保留，不计入上述链接数量。

Pi 加载器解析全部 59 个技能，同时读取 Pi 目录与共享目录时无缺失或重复冲突。变更中的 19 个 Python 文件、2 个 Shell 文件和 2 个 JSON 文件通过语法检查；`wizard` 的临时配置读写验证通过。未执行钉钉在线操作、完整文档渲染或真实服务配置向导。

## 2026-10-09：Matt 新工作流与上游技能同步

本次同步 6 个受管上游，更新 36 个现有技能，新增 3 个，移除 1 个上游已废弃技能。Matt 的 `engineering`、`productivity` 两组现在共 27 个技能；实验目录继续按原配置排除。

### 调用方式

下面的技能指令发在 agent 的聊天输入框中，代码块里的技能名不是终端命令。以 `implement-spec` 为例：

| 环境 | 显式调用示例 |
|---|---|
| Codex | `$implement-spec 按这份规格和关联工单完成实现` |
| Claude Code | `/implement-spec 按这份规格和关联工单完成实现` |
| Pi | `/skill:implement-spec 按这份规格和关联工单完成实现` |

后面的完整例子使用 Codex 写法，Claude Code 和 Pi 按此表替换前缀即可。Codex 的显式调用和自动发现方式见 [OpenAI 技能文档](https://learn.chatgpt.com/docs/build-skills)；Pi 的 `/skill:name` 与 `/reload` 写法见 [Pi 技能文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)。

`implement-spec`、`retro` 需要显式调用；`pr` 可以在写 PR 说明时由 agent 自动选用，也可以手动指定。

### 需要迁移：领域词汇文件改名

Matt 的领域建模、规格编写和审查流程现在读取 `GLOSSARY.md`，原来的约定是 `CONTEXT.md`。多领域项目对应从 `CONTEXT-MAP.md` 改为 `GLOSSARY-MAP.md`，词汇表仍按领域分别存放，ADR 仍在 `docs/adr/`。

现有项目按下面的顺序迁移：

1. 检查旧 `CONTEXT.md` 的用途。如果它只保存领域术语和定义，可以改为 `GLOSSARY.md`；如果还混有规格、操作说明或会话笔记，只迁出术语部分，保留其他内容及其原有用途。
2. 若使用了 `CONTEXT-MAP.md`，迁移映射文件和其中指向的各领域词汇表路径。
3. 更新项目已有的 `AGENTS.md`、`CLAUDE.md`、`docs/agents/domain.md` 及其他文档中的相关引用，检查是否仍有指向旧词汇表的链接。
4. 用 `domain-modeling` 核对新词汇表，确认术语、定义及跨领域关系没有遗漏。

可以直接发送：

```text
$domain-modeling 检查当前项目的 CONTEXT.md 和 CONTEXT-MAP.md。将领域术语迁移到 GLOSSARY.md / GLOSSARY-MAP.md，保留原文件中的规格和操作说明，并更新现有文档引用。完成后列出迁移的文件和保留的内容。
```

这次更新只同步技能，没有自动迁移其他项目的文档。没有旧词汇表的项目无需创建空文件，新流程会在明确第一批术语时再建立词汇表。格式见 [GLOSSARY-FORMAT.md](skills/domain-modeling/GLOSSARY-FORMAT.md)，读取约定见 [domain.md](skills/setup-matt-pocock-skills/domain.md)。

### 新增 implement-spec：一次实施整份规格

以前通常逐张工单调用 `implement`；现在可以把规格和已拆好的工单交给 `implement-spec`，由它按依赖关系调度可开始的任务，并把结果汇总到一个集成分支。

**使用前准备：**进入目标代码仓库，确认规格已定稿、每张工单有验收条件和阻塞关系，并已配置工单系统。并行实施依赖宿主提供子代理及 Git worktree 能力；缺少这些能力时，可以继续逐张调用 `implement`。

新项目首次使用 Matt 工程流程时，先调用 `setup-matt-pocock-skills`，确认后建立工单约定、triage 标签和文档入口。已有配置的项目先核对现状，保留已选用的工单系统。

下面以本地 Markdown 工单为例。逐条发送，上一阶段完成并确认后再进入下一阶段；`batch-export` 是示例功能名，使用时换成实际输出的目录：

```text
$setup-matt-pocock-skills 当前项目使用本地 Markdown 工单，请检查并配置工单路径、triage 状态和领域文档入口。

$to-spec 根据当前已确认的批量导出需求生成规格，保存到本地工单系统。

$to-tickets 将 .scratch/batch-export/spec.md 拆成可独立验证的纵向工单，列出 Blocked by 依赖关系。

$implement-spec 规格是 .scratch/batch-export/spec.md，工单在 .scratch/batch-export/issues/。按依赖关系完成整份规格，在一个集成分支上交付，并报告验证结果和工单状态。
```

预期过程与结果：

- 每个实施子代理使用独立 worktree 和分支，从集成分支开始，按已约定的测试边界使用 TDD；完成的任务陆续合入集成分支。
- 所有工单完成后，对集成分支运行一次 `code-review`，处理发现的问题，并清理实施子代理的 worktree。
- 使用 PR 收尾的工单系统，或用户明确要求 PR 时，会在首次合入代码后创建草稿 PR，完成审查后标为可审查；其他情况按工单系统约定记录完成状态并报告集成分支。

单张工单仍可用 `$implement .scratch/batch-export/issues/01-export-api.md`。自建的 `implement-codex` 保持原版，它没有随本次 Matt 更新自动改写。

完整流程见 [implement-spec](skills/implement-spec/SKILL.md)；本地工单路径见 [issue-tracker-local.md](skills/setup-matt-pocock-skills/issue-tracker-local.md)。

### 新增 pr：把改动、证据和合并风险写进 PR 说明

在代码和验证结果准备好后调用，提供比较基准及实际证据。例如：

```text
$pr 根据当前分支相对 main 的改动撰写 PR 说明，使用本次测试输出和已有截图作为证据，保存为 pr-body.md。
```

输出采用三个部分：

| 部分 | 应写什么 |
|---|---|
| Summary | 用最短的伪代码、调用树、文件树、结构差异或图说明关键变化 |
| Evidence | 列出修改前后的实际截图、命令输出或测试结果 |
| Merge Danger | 说明变更是否容易回滚，以及可能影响的范围 |

`pr` 负责组织说明，创建或更新 GitHub PR 是另一个操作。没有截图或测试结果时，应先补验证，不能把预计结果写成已验证。模板见 [pr](skills/pr/SKILL.md)。

### 新增 retro：复盘一次会话，提出环境改进

适合在实现或排障结束后、清空上下文之前调用：

```text
$retro 复盘本次实现，重点检查重复查找文件、测试遗漏和工具调用成本，按严重程度提出改进建议。
```

如果已经切换会话，提供日志的实际路径或明确指出要复盘的会话。没有指定时，默认复盘当前会话。

预期产物是一份按严重程度排序的建议，涵盖文档导航、自动检查、代码规范、agent 指令和工具使用。能机械判断的问题优先落到 lint、测试或 CI；需要判断的问题再进入代码规范。该技能的流程结束于提出建议，采纳哪些建议、是否修改环境由后续请求决定。

新版 `diagnosing-bugs` 的修复流程结束后，需要复盘时显式调用 `retro`。完整说明见 [retro](skills/retro/SKILL.md)。

### Matt 现有技能的使用变化

| 技能 | 更新后的用法与应看到的结果 |
|---|---|
| `implement` | 传入工单引用时，先读取工单并确认标题，再实施；例如 `$implement #123`。在多仓库场景中优先给完整工单 URL。 |
| `code-review` | 明确比较基准和规格来源，例如 `$code-review 审查当前分支相对 main 的改动，规格见 .scratch/batch-export/spec.md`；它会查找仓库内的规范文件，并分别报告 Standards 和 Spec 两个维度。 |
| `tdd` | 写测试前先约定公开测试边界，新版会说明每个边界能发现什么、覆盖不到什么；可发 `$tdd 先列出本次测试边界及各自覆盖和遗漏的行为，确认后逐步实施`。 |
| `diagnosing-bugs` | 如果通过修改代码或 fixture 人为制造失败，必须先用 diff 证明修改确实生效，再把失败当作测试有效的证据。 |
| `ask-matt` | 可以询问该用哪条流程，例如 `$ask-matt 我有一份规格和多张有依赖的工单，下一步怎么推进？`；新版会读取相关技能原文，再说明如何选择。 |

完整工作流见 [ask-matt](skills/ask-matt/SKILL.md)。

### Kami 1.12.0 → 1.17.0：统一检查和交付命令

文档填充完成后，可以用 `--deliver` 一次完成 HTML 检查、PDF 生成、PDF 检查和逐页图片导出。先准备好工作目录里的 `filled.html` 与按文档 schema 编写的 `content.json`，再在该目录运行：

```bash
python3 "$HOME/.agents/skills/kami/scripts/build.py" --doctor
python3 "$HOME/.agents/skills/kami/scripts/build.py" --check-content content.json
python3 "$HOME/.agents/skills/kami/scripts/build.py" --deliver filled.html content.json
```

修复输出中的 `ERROR` 后重跑，直到出现 `READY`。随后逐页查看导出的图片，检查截断、溢出、字体和页数；`READY` 只代表程序检查通过。`GAP` 会列出仍需补齐的数据，交付时应明确说明。

含公式的文档使用行内 `\( ... \)` 或块级 `\[ ... \]` LaTeX，`--deliver` 会在原 HTML 中把公式渲染成 MathJax SVG。首次使用公式前，需要 Node.js 20 或 22+，并安装公式运行时：

```bash
bash "$HOME/.agents/skills/kami/scripts/ensure_mathjax.sh"
```

落地页使用 `--deliver` 时只检查 HTML，仍需按语言和屏幕尺寸截图验证；需要可编辑 PPTX 时，在任务中明确说明。技能更新不会自动安装渲染依赖或字体。入口见 [Kami 交付说明](skills/kami/SKILL.md)。

### Playwright：把截图和视频附到 PR

新增的 [PR 附件说明](skills/playwright-cli/references/pr-attachments.md) 给出了截图、录屏与 GitHub PR 的衔接方法。先在运行中的应用上保存证据，例如应用地址为 `http://localhost:3000/settings` 时：

```bash
playwright-cli open http://localhost:3000/settings
playwright-cli screenshot --filename=settings-after.png
playwright-cli close
```

准备发布 PR 时，先准备好 `pr-body.md`，并确认 `gh pr create --help` 支持 `--attach`。上游文档要求 `gh` 2.99+，然后可运行：

```bash
gh pr create --title "fix(settings): preserve saved values" \
  --body-file pr-body.md \
  --attach './settings-after.png#Settings after saving'
```

该命令会创建 PR 并上传附件。图片须小于等于 10 MB，上传需要仓库 push 权限，支持 GitHub.com 和 GitHub Enterprise Cloud。视频可重复使用 `--attach` 添加，录制方法见 [video-recording.md](skills/playwright-cli/references/video-recording.md)。

本次核对时，本机 `playwright-cli` 为 0.1.22，`gh` 为 2.87.3，后者尚无 `--attach`。截图可以先保存到本地，使用附件命令前需升级 `gh`；本次仅更新了技能文件。

### Waza：明确任务范围后调用

调用名称保持不变，这次更新补充了更明确的任务范围和技术说明规则：

- `think` 收到继续实施的明确指令后，会沿已确定的方案执行；如果只是让它评估是否值得做，仍以评估结果结束。
- `check` 的审查请求默认返回发现；需要连同修复一起完成时，明确说「审查并修复这些问题」。
- `health` 支持静态配置审查的明确范围，例如「只检查当前项目的 AGENTS.md、skills 和配置」；按此范围执行时不会把会话历史纳入审查。
- `write` 新增技术说明的消歧规则，可指定「检查这段安装说明的前置条件、执行顺序和失败后的处理，保留原有含义」。

### 移除 resolving-merge-conflicts

Matt 已在 [移除提交](https://github.com/mattpocock/skills/commit/daa01d8aa68ad5c61b68970ec2018d0ce9567be6) 中删除该技能，这不是改名，`pr` 也不是它的替代品。

现有项目若写有对该技能的固定调用，改为直接说明需要解决哪个 merge 或 rebase 冲突，并沿项目自己的 Git 规则处理。此次旧目录保留在 `.sync-skills-recovery/resolving-merge-conflicts.prune.*`，三边旧软链接及恢复目录中的相应断链已清理。

### 同步范围与验证

| 上游 | 本次同步到的提交 |
|---|---|
| mattpocock/skills | [b0618bc](https://github.com/mattpocock/skills/commit/b0618bc436ad893b3c5e84e55fba86586d34a404) |
| tw93/Waza | [6b6c736](https://github.com/tw93/Waza/commit/6b6c736561eaf24c4d1c5360c3c90767ab470805) |
| tw93/kami | [5a7fa34](https://github.com/tw93/kami/commit/5a7fa34e3804199e6fa28eea1c16057ece2f8f0f) |
| microsoft/playwright-cli | [b85c7a7](https://github.com/microsoft/playwright-cli/commit/b85c7a736bb473bf55b584e54a09ffa698d6d871) |
| herdrdev/herdr | [2563803](https://github.com/herdrdev/herdr/commit/2563803dca97c040beaf3dc3acdcb5a3221b4238) |
| Agents365-ai/365-skills | [bc55bf9](https://github.com/Agents365-ai/365-skills/commit/bc55bf9869f366d33863655ba11d6b8e2c728fc6) |

更新后运行同步脚本，6 个受管上游均无内容或文件模式差异；同步工具的 47 项测试通过。Codex 的 43 个、Claude 的 44 个、Pi 的 44 个受管软链接有效，包括恢复目录在内无断链。Pi 的加载器可解析全部 44 个本地技能，同时扫描自身目录和共享目录时没有重复冲突。

`dws`、自建的 `implement-codex` / `accept-issue` / `land-issue`、手工维护的 `humanizer-zh` 保留原内容。`dws` 已登记为本地保留项，不跟随本次受管上游更新。

这里的验证覆盖同步完整性、技能格式与软链接；没有逐个执行实现工单、发布 PR、渲染文档等完整业务流程。
