"""
配置管理器
"""

import json
import os
import tkinter as tk
from typing import Dict, Any

from .constants import (
    DEFAULT_START_X,
    DEFAULT_START_Y,
    DEFAULT_CELL_WIDTH,
    DEFAULT_CELL_HEIGHT,
    DEFAULT_AUTO_TAP,
    CONFIG_FILE
)


class ConfigManager:
    """管理应用配置"""

    def __init__(self):
        self.config_file = CONFIG_FILE
        self.config: Dict[str, Any] = {
            "startX": str(DEFAULT_START_X),
            "startY": str(DEFAULT_START_Y),
            "cellWidth": str(DEFAULT_CELL_WIDTH),
            "cellHeight": str(DEFAULT_CELL_HEIGHT),
            "autoTap": DEFAULT_AUTO_TAP
        }

    def load(self) -> Dict[str, Any]:
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)

                # 合并配置，空值使用默认值
                for key, default_value in self.config.items():
                    if key in loaded_config and loaded_config[key]:
                        self.config[key] = loaded_config[key]
            except Exception as e:
                print(f"加载配置失败: {e}")

        return self.config

    def save(self) -> bool:
        """保存配置"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def update(self, key: str, value: Any):
        """更新配置项"""
        self.config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)

    def load_to_entries(self, entries: Dict[str, tk.Entry]):
        """
        将配置加载到输入框

        Args:
            entries: 输入框字典，键为配置项名
        """
        config = self.load()

        for key, entry in entries.items():
            entry.delete(0, tk.END)
            value = config.get(key, "")
            if value:
                entry.insert(0, str(value))

    def save_from_entries(self, entries: Dict[str, tk.Entry]):
        """
        从输入框保存配置

        Args:
            entries: 输入框字典，键为配置项名
        """
        for key, entry in entries.items():
            self.config[key] = entry.get()

        self.save()