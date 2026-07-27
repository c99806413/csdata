import json
import re
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog

# ======================== 品牌处理（不再依赖映射文件） ========================

def normalize_brand_name(brand_name):
    """
    品牌名归一化：直接返回原始品牌名（去除首尾空格）
    因为硬盘上的文件夹名已经是规范格式（如 "华为（HUAWEI）"）
    """
    if not brand_name:
        return "未知品牌"
    return brand_name.strip()


# ======================== 工具函数 ========================
def normalize_id(name):
    if not name:
        return "unknown"
    return ''.join(c if c.isalnum() else '_' for c in name.strip()).lower()


def get_manufacturer(item):
    if isinstance(item, dict):
        if "manufacturer" in item and item["manufacturer"]:
            return item["manufacturer"]
        meta = item.get("metadata", {})
        if "manufacturer" in meta and meta["manufacturer"]:
            return meta["manufacturer"]
    return None


def get_series(item):
    if isinstance(item, dict):
        if "series" in item and item["series"]:
            return item["series"]
        meta = item.get("metadata", {})
        if "series" in meta and meta["series"]:
            return meta["series"]
    return "无系列"


def get_model_name(item, fallback):
    if isinstance(item, dict):
        if "name" in item and item["name"]:
            return item["name"]
        meta = item.get("metadata", {})
        if "name" in meta and meta["name"]:
            return meta["name"]
    return fallback


def get_opendb_id(item, fallback):
    if isinstance(item, dict):
        if "opendb_id" in item and item["opendb_id"]:
            return item["opendb_id"]
        if "id" in item and item["id"]:
            return item["id"]
    return fallback


def get_relative_file_path(source_file, data_dir):
    try:
        rel_path = Path(source_file).relative_to(data_dir)
        return str(rel_path).replace('\\', '/')   # 去掉 "js/data/"
    except ValueError:
        return source_file


def fix_json_content(content):
    """
    修复常见的JSON格式错误：移除对象和数组末尾的多余逗号
    """
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    return content


def extract_models_from_json(file_path, series_name=None):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        fixed_content = fix_json_content(raw_content)
        data = json.loads(fixed_content)
    except Exception as e:
        print(f"⚠️ 跳过无效JSON文件 {file_path}: {e}")
        return []

    models = []

    def walk(obj):
        if isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            if "opendb_id" in obj or "id" in obj:
                obj['_source_file'] = str(file_path)
                if series_name:
                    obj['series'] = series_name
                models.append(obj)
            if "children" in obj and isinstance(obj["children"], list):
                for child in obj["children"]:
                    walk(child)

    walk(data)
    return models


def build_series_nodes(models, data_dir):
    series_groups = defaultdict(list)
    for model in models:
        series = get_series(model)
        series_groups[series].append(model)

    series_nodes = []
    for series_name, series_models in series_groups.items():
        series_id = normalize_id(series_name)
        series_node = {
            "id": series_id,
            "name": series_name,
            "type": "series",
            "children": []
        }
        for model in series_models:
            model_id = get_opendb_id(model, "unknown")
            model_name = get_model_name(model, model_id)
            source_file = model.get('_source_file', '')
            file_path_str = get_relative_file_path(source_file, data_dir) if source_file else ""

            model_node = {
                "id": model_id,
                "name": model_name,
                "type": "model",
                "file": file_path_str
            }
            series_node["children"].append(model_node)

        if series_node["children"]:
            series_nodes.append(series_node)

    return series_nodes


def build_brand_from_models(models, data_dir):
    """
    ★ 改动：直接使用文件夹名作为品牌名，不再依赖映射文件
    因为用户已经通过重命名脚本将文件夹名改成了规范格式
    """
    brand_groups = defaultdict(list)
    for model in models:
        brand = get_manufacturer(model)
        if not brand:
            brand = "未知品牌"
        normalized_brand = normalize_brand_name(brand)
        brand_groups[normalized_brand].append(model)

    brand_nodes = []
    for brand_name, brand_models in brand_groups.items():
        brand_id = normalize_id(brand_name)
        brand_node = {
            "id": brand_id,
            "name": brand_name,
            "type": "brand",
            "children": []
        }
        series_nodes = build_series_nodes(brand_models, data_dir)
        brand_node["children"].extend(series_nodes)
        if brand_node["children"]:
            brand_nodes.append(brand_node)

    return brand_nodes


# ======================== 核心：扫描目录 ========================
def scan_directory(current_path, data_dir, depth=0):
    """
    物理文件夹 = 导航节点
    ★ 改动：品牌名直接使用文件夹名，不再做映射转换
    """
    node = {
        "id": normalize_id(current_path.name),
        "name": current_path.name,
        "type": "",
        "children": []
    }

    subdirs = []
    json_files = []
    for item in current_path.iterdir():
        if item.is_dir():
            subdirs.append(item)
        elif item.is_file() and item.suffix == '.json':
            if item.name not in ['category_nav.json', '_index.json']:
                json_files.append(item)

    rel_path = current_path.relative_to(data_dir)
    depth = len(rel_path.parts)

    # 1. 递归处理子目录
    child_nodes = []
    for sub in subdirs:
        child = scan_directory(sub, data_dir, depth + 1)
        if child and child.get("children"):
            child_nodes.append(child)

    # 2. 提取当前目录下所有 JSON 中的型号
    all_models = []
    for jf in json_files:
        models = extract_models_from_json(jf, series_name=jf.stem)
        if models:
            all_models.extend(models)

    has_models = len(all_models) > 0
    has_children = len(child_nodes) > 0

    # 3. 没有任何内容 → 不显示
    if not has_models and not has_children:
        return None

    # 4. 根目录
    if depth == 0:
        node["type"] = "root"
        node["children"] = child_nodes
        return node if node["children"] else None

    # 5. 品类层级 (depth=1)
    if depth == 1:
        node["type"] = "category"
        node["children"] = child_nodes
        return node if node["children"] else None

    # 6. 有 JSON 数据时，提取系列和型号
    node["children"] = child_nodes.copy()

    if has_models:
        # 判断当前品类是否是"电脑配件"
        category_name = None
        if depth >= 2:
            temp_path = current_path
            for _ in range(depth - 1):
                temp_path = temp_path.parent
            category_name = temp_path.name

        if category_name == "电脑配件":
            # 电脑配件：从数据中读取 manufacturer 生成品牌
            node["type"] = "subcategory"
            brand_nodes = build_brand_from_models(all_models, data_dir)
            node["children"].extend(brand_nodes)
        else:
            # ★ 改动：直接使用当前文件夹名作为品牌名
            node["type"] = "brand" if depth == 2 else "subcategory"
            series_nodes = build_series_nodes(all_models, data_dir)
            node["children"].extend(series_nodes)

    if not node["children"]:
        return None

    return node


def main():
    root = tk.Tk()
    root.withdraw()
    data_dir_str = filedialog.askdirectory(title="请选择 data 文件夹")
    if not data_dir_str:
        print("未选择目录，退出。")
        return

    data_dir = Path(data_dir_str)
    if not data_dir.exists():
        print(f"错误：目录 {data_dir} 不存在")
        return

    print(f"📁 数据目录: {data_dir}")

    # ★ 改动：不再加载品牌映射文件

    root_node = scan_directory(data_dir, data_dir, 0)

    if not root_node or not root_node.get("children"):
        print("⚠️ 没有找到任何有效数据")
        return

    categories = root_node["children"]

    nav = {
        "version": "1.0",
        "categories": categories
    }

    output_file = data_dir / "category_nav.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(nav, f, ensure_ascii=False, separators=(',', ':'))

    print(f"✅ 导航索引已生成：{output_file}")
    print(f"📊 共 {len(categories)} 个品类")

    input("\n按 Enter 键退出...")


if __name__ == "__main__":
    main()