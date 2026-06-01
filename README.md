# 临沂市卫生健康委员会自建 RSS

这个项目用于把 `https://wsjsw.linyi.gov.cn/` 这类没有官方 RSS 的政府网站，转换成可订阅的 `rss.xml`。

## 默认监控栏目

当前脚本默认监控：

- 首页
- 要闻新闻
- 公示公告
- 政策法规
- 办事指南
- 资料下载

你可以在 `linyi_wsjsw_rss.py` 里的 `CHANNELS` 继续添加栏目。

## 本地运行

```bash
pip install -r requirements.txt
python linyi_wsjsw_rss.py
```

运行后会生成：

```bash
rss.xml
```

## GitHub 自动更新

仓库已经包含 GitHub Actions 配置：

```bash
.github/workflows/rss.yml
```

默认每 6 小时运行一次，并把生成的 `rss.xml` 自动提交回仓库。

## GitHub Pages 发布

1. 把本项目上传到一个 GitHub 仓库。
2. 进入仓库 `Settings`。
3. 进入 `Pages`。
4. Source 选择 `Deploy from a branch`。
5. Branch 选择 `main`，目录选择 `/root`。
6. 保存。

之后 RSS 地址一般是：

```text
https://你的用户名.github.io/仓库名/rss.xml
```

把这个地址放进 Feedly、Inoreader、Reeder、NetNewsWire 等 RSS 阅读器即可。

## 手动触发更新

进入 GitHub 仓库：

`Actions` → `Generate RSS` → `Run workflow`

## 添加新栏目

打开 `linyi_wsjsw_rss.py`，修改：

```python
CHANNELS = {
    "首页": "https://wsjsw.linyi.gov.cn/",
    "要闻新闻": "https://wsjsw.linyi.gov.cn/ywxw.htm",
    "公示公告": "https://wsjsw.linyi.gov.cn/ywxw/gsgg.htm",
}
```

继续加一行即可：

```python
"新栏目名称": "栏目URL",
```

## 注意

部分文章可能跳转到微信、新华社、人民网等外部链接。当前脚本默认只保留 `wsjsw.linyi.gov.cn` 站内文章。如果你想保留外链，可以在 `is_probably_article_link()` 函数里放开外链过滤。
