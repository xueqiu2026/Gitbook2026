# GitBook Multi-Strategy Downloader v5.0 Ultimate 🚀

**最强 GitBook 下载利器 - 融合多种策略，支持 PDF 导出与本地交互式阅读！**

专为网络安全工程师与研究人员设计，支持离线备份、竞品分析与深度阅读。

## 🌟 核心特性 (v5.0 新增)

### 1. 🔥 Fusion 融合策略 (Fusion Strategy)
不再受限于单一方法的局限。Fusion 策略同时运行：
- **智能探针 (Smart Probe)**: 自动探测并下载原生 Markdown 文件 (质量最高)。
- **Sitemap 解析**: 覆盖所有隐藏页面。
- **侧边栏结构**: 1:1 完美还原原始文档目录层级。
- **混合纠错**: 自动修正 "Untitled" 标题与重复内容，生成完美的 Ultimate 版本。

### 2. 📖 交互式阅读器 (Clean Reader)
自带高性能本地 Web 阅读器 (`viewer.py`)：
- **沉浸式阅读**: 左侧目录树，右侧内容区，支持深色模式 (Dark Mode)。
- **智能搜索**: 快速查找本地文档库。
- **PDF 导出**: ✨ **新增** - 一键将当前文档导出为 PDF 格式。

### 3. 🛡️ 稳如泰山
- **本地化资源**: 自动下载所有图片附件，修正链接，确保离线 100% 可用。
- **智能去重**: 严格的 URL 归一化算法，拒绝重复页面。

---

## ⚡ 快速开始

### 1. 安装
```bash
git clone https://github.com/your-repo/gitbook_downloader.git
cd gitbook_downloader
pip install -r requirements.txt
```

### 2. 启动阅读器 (推荐)
这是最简单的使用方式，提供图形化界面管理下载任务。
```bash
python viewer.py
```
- 访问 `http://localhost:8000`
- 输入 GitBook URL (如 `https://docs.audiera.fi`)
- 点击 Download，稍等片刻即可享受。

### 3. 命令行高级用法 (CLI)

#### 基础下载
```bash
python main.py https://target.gitbook.io/docs -o output.md
```

#### 启用 Fusion 终极模式 (推荐)
```bash
python main.py https://target.gitbook.io/docs --strategy fusion --use-selenium
```

#### 仅下载特定章节
```bash
python main.py https://target.gitbook.io/docs/api-docs/ --section-path api-docs
```

## 🛠️ 策略详解

| 策略 | 速度 | 质量 | 适用场景 |
|------|------|------|----------|
| **Fusion (推荐)** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **完美主义者**。融合多源数据，提供最佳结构与内容。 |
| **Github** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 目标关联了开源 Git 仓库。速度极快。 |
| **Sitemap** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 目标有 `sitemap.xml` 但无 Github。 |
| **Scraping** | ⭐⭐ | ⭐⭐⭐⭐ | 最后的防线。模拟浏览器逐页爬取，适用于复杂前端。 |

## 📦 项目结构

```
gitbook_downloader/
├── viewer.py                  # Web 阅读器入口 (GUI)
├── main.py                    # 命令行入口 (CLI)
├── gitbook_multi_downloader.py # 核心调度器
├── web_server.py              # 后端 API 服务
├── templates/                 # 前端界面源码
├── strategies/                # 策略模块 (Fusion, Scraping, etc.)
└── library/                   # 下载的文档存放区
```

## 📄 依赖要求
- Python 3.8+
- Chromium (如果使用 Selenium 策略)

## 🤝 贡献
欢迎提交 Issue 或 PR。致力于打造最通用的 GitBook 离线化工具。

## 📜 License
MIT License

## ⚖️ 免责声明 (Disclaimer)

1.  **技术交流**: 本项目仅供网络安全技术交流与 Python 学习使用。
2.  **非商用**: 严禁将本项目及其衍生代码用于任何形式的商业用途或非法行为。
3.  **合法合规**: 使用本工具下载文档时请遵守目标网站的 `robots.txt` 协议及版权声明。
4.  **免责**: 开发者不对因使用本工具造成的任何直接或间接后果（包括但不限于账号封禁、法律纠纷）负责。使用者需自行承担风险。

