"""
配置文件加载/同步工具

启动时以 client.example.yml 为模板核对 client.yml：
- 缺少的配置项自动补充默认值（保留用户已修改的值）
- 多余/已废弃的配置项自动移除
- 保留 example 文件中的注释，写回时格式统一
"""
import logging
import os
import shutil

import ruamel.yaml as YAML
from ruamel.yaml.scalarstring import (
    DoubleQuotedScalarString,
    FoldedScalarString,
    LiteralScalarString,
    SingleQuotedScalarString,
)

logger = logging.getLogger(__name__)

yaml = YAML.YAML(typ="rt")

# 默认配置文件名
CONFIG_FILE = "client.yml"
EXAMPLE_FILE = "client.example.yml"


def _to_plain(value):
    """将 ruamel 的带注释容器转换为普通 dict/list，便于比较与使用"""
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _preserve_scalar_style(template: str, user: str) -> str:
    """沿用模板的引号风格，避免 "123456" 这类值被写成裸标量后变成数字"""
    if isinstance(template, DoubleQuotedScalarString):
        return DoubleQuotedScalarString(user)
    if isinstance(template, SingleQuotedScalarString):
        return SingleQuotedScalarString(user)
    if isinstance(template, (LiteralScalarString, FoldedScalarString)):
        return type(template)(user)
    return user


def _check_type(name: str, template, user):
    """模板与用户值的类型不一致时给出提示（仍以用户值为准）"""
    mismatched = (
        isinstance(template, bool) != isinstance(user, bool)
        or isinstance(template, str) != isinstance(user, str)
        or isinstance(template, (int, float)) != isinstance(user, (int, float))
    )
    if mismatched:
        logger.warning(
            f"配置项 {name} 的类型({type(user).__name__})与预期({type(template).__name__})不一致，请检查"
        )


def _merge(template, user, name: str = ""):
    """以模板结构为准合并配置：缺失项取模板默认值，多余项丢弃"""
    if isinstance(template, dict):
        if not isinstance(user, dict):
            # 类型不符，回退为模板默认值
            logger.warning(f"配置项 {name} 应为字典，已使用默认值")
            return template
        for key, template_value in template.items():
            if key in user:
                template[key] = _merge(template_value, user[key], str(key))
        return template

    if isinstance(template, (list, tuple)):
        if not isinstance(user, list):
            logger.warning(f"配置项 {name} 应为列表，已使用默认值")
            return template
        # 继承模板的列表书写风格（流式/块状）
        sequence = YAML.CommentedSeq(user)
        if isinstance(template, YAML.CommentedSeq):
            if template.fa.flow_style():
                sequence.fa.set_flow_style()
            else:
                sequence.fa.set_block_style()
        return sequence

    # None 视为未配置，回退模板默认值
    if user is None:
        return template

    _check_type(name, template, user)

    if isinstance(template, str) and isinstance(user, str):
        return _preserve_scalar_style(template, user)

    return user


def load_config(config_path: str = CONFIG_FILE, example_path: str = EXAMPLE_FILE) -> dict:
    """加载配置，并在配置与示例文件不一致时同步写回"""
    if not os.path.exists(example_path):
        raise FileNotFoundError(f"未找到示例配置文件: {example_path}")

    if not os.path.exists(config_path):
        shutil.copy(example_path, config_path)
        logger.info(f"未找到配置文件，已从 {example_path} 生成 {config_path}")

    with open(example_path, "r", encoding="utf-8") as f:
        template = yaml.load(f)

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.load(f) or {}

    merged = _merge(template, _to_plain(user_config))

    if _to_plain(merged) != _to_plain(user_config):
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(merged, f)
        logger.info(f"配置文件已更新：缺少或多出的配置项已按 {example_path} 同步")

    return _to_plain(merged)


def save_config(config: dict, config_path: str = CONFIG_FILE, example_path: str = EXAMPLE_FILE) -> None:
    """在保留注释与结构的前提下写回配置"""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.load(f) or {}
    else:
        with open(example_path, "r", encoding="utf-8") as f:
            data = yaml.load(f)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(_merge(data, _to_plain(config)), f)
