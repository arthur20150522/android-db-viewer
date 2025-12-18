# Android DB Viewer

**Android DB Viewer** 是一个专为 Android 开发者设计的 Web 可视化工具，旨在通过 ADB 快速访问、查看和查询 Root 设备上的应用数据库（SQLite）。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Flask](https://img.shields.io/badge/flask-2.0+-orange.svg)

## 🚀 核心功能

- **设备管理**：自动检测连接的 Android 设备并验证 Root 权限。
- **应用浏览**：快速搜索和列出设备上安装的应用包名。
- **数据库获取**：利用 Root 权限自动发现并拉取应用私有目录 (`/data/data/...`) 下的 SQLite 数据库。
- **数据可视化**：
  - 以表格形式浏览数据库表结构和数据。
  - 支持分页查看，轻松处理大量数据。
- **SQL 编辑器**：内置 SQL 编辑器（支持语法高亮），可执行自定义查询语句。
- **Web 界面**：基于 Bootstrap 5 的现代化响应式界面，操作流畅。

## 🛠️ 安装与运行

### 环境要求
- Python 3.8+
- Android SDK Platform-Tools (确保 `adb` 命令在环境变量中)
- **已 Root** 的 Android 设备 (并开启 USB 调试)

### 快速开始

1. **克隆仓库**
   ```bash
   git clone git@github.com:arthur20150522/android-db-viewer.git
   cd android-db-viewer
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **运行应用**
   ```bash
   python app.py
   ```

4. **访问界面**
   打开浏览器访问：[http://localhost:5000](http://localhost:5000)

## 📖 使用指南

1. **连接设备**：将手机通过 USB 连接电脑，确保 `adb devices` 能识别到设备。
2. **选择设备**：在网页左上角下拉框选择目标设备。如果设备已 Root，状态图标将显示为绿色。
3. **查找应用**：在左侧搜索框输入应用包名关键词（如 `com.tencent`），点击目标应用。
4. **加载数据库**：点击应用下方的数据库文件名，工具会自动将其拉取到本地临时目录。
5. **浏览数据**：点击表名即可查看数据。
6. **执行 SQL**：切换到 "SQL Editor" 标签页，输入 SQL 语句并点击 "Run Query"。

## 📄 项目规划

详细的产品规格和设计文档请参考：[项目规格说明书](docs/SPECIFICATION.md)

## 📝 目录结构

```
android-db-viewer/
├── app.py                  # Flask 主应用入口
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖列表
├── modules/                # 后端核心模块
│   ├── adb_interface.py    # ADB 通信封装
│   └── db_manager.py       # SQLite 数据库操作
├── static/                 # 前端静态资源 (JS/CSS)
├── templates/              # HTML 模板
├── temp/                   # 临时文件存储 (自动清理)
└── docs/                   # 文档目录
```

## 🤝 贡献

欢迎提交 Issue 或 Pull Request 来改进这个工具！

## License

MIT License
