# mv2dir - 文件整理工具集

一个包含多个文件整理工具的Python项目，帮助用户自动化管理和组织各种类型的文件。

## 项目结构

```
mv2dir/
├── file_organizer/     # 通用文件整理工具
├── mv2moviedir/       # 电影文件整理工具
├── mv2tvdir/          # 电视剧文件整理工具
└── README.md          # 项目说明文档
```

## 工具介绍

### 1. File Organizer - 通用文件整理工具

**位置**: `file_organizer/`

**功能**: 按文件名将文件自动分类到对应的子目录中

**特点**:
- 🗂️ 智能分类：根据文件名自动创建目录并分类文件
- 🎬 字幕文件支持：智能处理字幕文件，去除语言标识符
- 🔒 安全操作：避免覆盖已存在的文件
- 🌍 多语言支持：完美支持中文文件名

**使用方法**:
```bash
cd file_organizer/
python3 file_organizer.py [目录路径]
```

### 2. mv2moviedir - 电影文件整理工具

**位置**: `mv2moviedir/`

**功能**: 将电影文件按年代分组整理到目录结构中

**特点**:
- 🎬 电影识别：自动识别电影文件和相关字幕
- 📅 年代分组：按年代（如2020s, 2010s）组织文件
- 🎯 智能匹配：支持多种文件命名格式
- 📊 详细统计：显示处理结果和统计信息

**使用方法**:
```bash
cd mv2moviedir/
python3 mv2moviedir.py [选项]
```

### 3. mv2tvdir - 电视剧文件整理工具

**位置**: `mv2tvdir/`

**功能**: 将电视剧文件移动到按剧名/季级组织的目录结构中

**特点**:
- 📺 电视剧识别：自动识别剧集文件格式（S01E01等）
- 🗂️ 季级组织：按剧名和季数创建目录结构
- 🎯 分辨率过滤：支持按分辨率和编码筛选文件
- 🧹 源目录清理：可选择性删除空的源目录

**使用方法**:
```bash
cd mv2tvdir/
python3 mv2tvdir.py <源目录> <目标目录> [选项]
```

## 系统要求

- Python 3.6+
- 支持的操作系统：Windows, macOS, Linux

## 安装和使用

1. **克隆项目**:
   ```bash
   git clone <repository-url>
   cd mv2dir
   ```

2. **选择需要的工具**:
   ```bash
   # 进入对应的工具目录
   cd file_organizer/    # 或 mv2moviedir/ 或 mv2tvdir/
   ```

3. **查看帮助信息**:
   ```bash
   python3 <工具名>.py --help
   ```

4. **运行示例**:
   ```bash
   python3 example.py    # 查看使用示例（如果有）
   ```

## 详细文档

每个工具目录下都包含详细的README.md文档和使用示例：

- [File Organizer 文档](file_organizer/README.md)
- [mv2moviedir 文档](mv2moviedir/README.md)
- [mv2tvdir 文档](mv2tvdir/README.md)

## 许可证

本项目采用 MIT 许可证。详情请参阅各工具目录下的 LICENSE 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这些工具！

## 更新日志

- **v1.0.0**: 初始版本，包含三个独立的文件整理工具
  - file_organizer: 通用文件整理
  - mv2moviedir: 电影文件整理（支持年代分组）
  - mv2tvdir: 电视剧文件整理（v1.0.3）