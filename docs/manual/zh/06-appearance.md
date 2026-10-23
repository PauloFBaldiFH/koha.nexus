# 6. OPAC 与 staff 外观

[目录](README.md)

## 先读取，再小步应用

用 o 打开 **OPAC and Staff Appearance**。公共 OPAC 与专业 staff 各有设置。先 **Sync current OPAC settings** 读取现值；同步不应用新主题。每次只改一组选项，检查颜色、可读性和图像。

**Preview** 展示将写入的 CSS、JavaScript 和内容，不是完整浏览器效果。**Apply** 会先 backup，再在确认后写入。随后在浏览器检查两端首页、搜索、记录、登录和小屏幕显示。OPAC 写入 `OpacUserCSS`/`OpacUserJS`，staff 使用 `IntranetUserCSS`，必要时还有 `IntranetUserJS`。本馆自定义块会保留，但仍可能视觉冲突。

纹理、模糊、透明度、圆角、强调色和背景须保证对比度。明暗切换与默认主题是独立设置。staff 有自己的色彩、顶栏、快捷搜索、模块卡片、表格密度和字号。**Apply color theme to Staff Client** 启用其色彩；**Copy OPAC preset** 只填表，仍需 **Apply** 才写入。

## 图像、轮播与按钮

图像可来自服务器文件、所列托管服务或直接 HTTPS URL。支持 PNG、JPEG、GIF、WebP、ICO，拒绝 SVG。馆员电脑上的文件须先让服务器可访问。确认使用权，并为登录图像提供屏幕阅读器说明。托管网页地址未必是图片直链；不要在公开页面发布内部信息。

轮播可展示新到或 Koha 列表。列表编号取 URL 的 `shelfnumber=`。检查题名、数量、样式、速度、自动播放，用 **Refresh carousel** 更新。缺封面不表示书目消失，外部封面服务需要网络。

OPAC 快捷按钮与 staff 首页按钮分别设置。检查文字、目标 URL、打开方式和顺序。**Add a button** 添加一行，行内移除按钮在应用前删除该项。

## 登录、新闻、页脚与移除

登录框可配置图像、说明与 HTML，流程会过滤脚本、样式和事件处理器。不要把仅供员工的内部指引放在访客可见区域。

两端新闻各有标题、文本、按钮，由面板管理为 Koha 条目，不替换图书馆独立创建的新闻。页脚按 `Field: value` 输入，附加链接用 `Text|URL`，最多六个，只填写公开信息。

**Remove** 先确认和 backup，再移除面板主题块，同时保留本馆自定义。它不是全库 restore，不回退其他管理操作。若只错了一张图或一个颜色，应修正对应组选项再应用；失败时保存消息供排查。

## 已核对的源码

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
