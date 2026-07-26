import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from collections import defaultdict

# ======================== 工具函数 ========================

def safe_opendb_id(name)
    生成安全的opendb_id（仅字母、数字、下划线）
    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', name)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned.lower()


def merge_values(values)
    合并多个值，去重后按原始顺序用斜杠连接
    seen = []
    for v in values
        if v not in seen
            seen.append(v)
    return ''.join(seen)


def extract_series_name(name)
    从 name 中提取基础系列名（去掉括号内容）
    if not name
        return 
    cleaned = re.sub(r'[（(][^）)][）)]', '', name)
    cleaned = re.sub(r's+', ' ', cleaned).strip()
    return cleaned


def process_ssd_file(file_path, backup=True)
    处理单个固态硬盘JSON文件：合并所有记录为1条
    try
        with open(file_path, 'r', encoding='utf-8') as f
            data = json.load(f)
        
        if not data or not isinstance(data, list)
            return False, 文件格式不是列表或为空

        # 如果只有一条记录，检查是否需要清理名称
        if len(data) == 1
            original_name = data[0].get('name', '')
            clean_name = extract_series_name(original_name)
            if clean_name and clean_name != original_name
                data[0]['name'] = clean_name
                data[0]['opendb_id'] = safe_opendb_id(clean_name)
                if 'series' in data[0]
                    data[0]['series'] = clean_name
                with open(file_path, 'w', encoding='utf-8') as f
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True, f已清理单条记录的名称 {clean_name}
            return False, 仅有一条记录，无需合并

        # 多条记录：提取系列名
        first_name = data[0].get('name', '')
        series_name = extract_series_name(first_name)
        if not series_name
            series_name = data[0].get('series', '未知系列')

        manufacturer = data[0].get('manufacturer', '')

        # ===== 合并所有记录 =====
        merged_metadata = {}
        all_capacities = []

        for item in data
            metadata = item.get('metadata', {})
            # 收集容量
            capacity = metadata.get('存储容量', '')
            if capacity
                all_capacities.append(capacity)
            # 合并其他字段
            for key, value in metadata.items()
                if key not in merged_metadata
                    merged_metadata[key] = [value]
                else
                    if value not in merged_metadata[key]
                        merged_metadata[key].append(value)

        # 整理合并后的值
        for key in merged_metadata
            values = merged_metadata[key]
            if len(set(values)) == 1
                # 所有值相同，只保留一个
                merged_metadata[key] = values[0]
            else
                # 值不同，用斜杠连接
                merged_metadata[key] = merge_values(values)

        # 确保存储容量字段包含所有容量（如果存在）
        if all_capacities
            merged_metadata['存储容量'] = merge_values(all_capacities)

        # 生成合并后的记录
        new_item = {
            name series_name,
            manufacturer manufacturer,
            series series_name,
            opendb_id safe_opendb_id(series_name),
            metadata merged_metadata
        }

        # ===== 备份并写入 =====
        if backup
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            if backup_path.exists()
                backup_path.unlink()
            file_path.rename(backup_path)

        with open(file_path, 'w', encoding='utf-8') as f
            json.dump([new_item], f, ensure_ascii=False, indent=2)

        original_count = len(data)
        return True, f合并成功 {original_count}条 → 1条，系列 {series_name}

    except Exception as e
        return False, f处理失败 {e}


def process_directory(root_dir, backup=True)
    递归处理目录下所有JSON文件
    root_path = Path(root_dir)
    if not root_path.exists()
        return 目录不存在

    json_files = list(root_path.glob('.json'))
    json_files = [f for f in json_files if not f.name.endswith('.backup')]

    if not json_files
        return 未找到任何 JSON 文件

    result_lines = []
    success_count = 0
    total_files = len(json_files)

    for idx, file_path in enumerate(json_files, 1)
        success, msg = process_ssd_file(file_path, backup)
        if success
            success_count += 1
        result_lines.append(f[{idx}{total_files}] {file_path.relative_to(root_path)} {msg})

    result_text = n.join(result_lines)
    summary = f处理完成！共 {total_files} 个文件，成功处理 {success_count} 个。nn详细结果：n{result_text}
    return summary


def main()
    root = tk.Tk()
    root.withdraw()

    dir_path = filedialog.askdirectory(
        title=请选择固态硬盘数据目录（如：...data电脑配件固态硬盘）
    )
    if not dir_path
        messagebox.showinfo(提示, 未选择目录，程序退出)
        return

    backup_choice = messagebox.askyesno(
        备份,
        是否备份原文件（将原文件重命名为 .json.backup）？nn建议选择“是”，以便出错时恢复。
    )
    if backup_choice is None
        return

    if not messagebox.askyesno(
        确认,
        f将处理目录：{dir_path}n及其所有子文件夹中的 JSON 文件。nn
        f操作内容：n
        f  1. 同一系列的所有容量版本合并为1条n
        f  2. 存储容量用斜杠连接（如 120GB240GB480GB）n
        f  3. 其他差异字段也用斜杠连接n
        f  4. name 保留基础系列名（去掉括号内容）nn
        f⚠️ 原文件将被覆盖（备份文件为 .backup）nn是否继续？
    )
        return

    result = process_directory(dir_path, backup_choice)
    print(result)
    messagebox.showinfo(完成, f处理完成！nn{result.split(chr(10))[0]}nn详情请查看控制台输出。)


if __name__ == __main__
    main()