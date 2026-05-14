#!/usr/bin/env python3
"""
honesty-check — 诚实自检脚本

用法：
  python honesty-check.py --input "我的回答内容"        # 自检单条回答
  python honesty-check.py --log-dont-know              # 记录一次"不知道"
  python honesty-check.py --stats                       # 查看诚实记录统计
  python honesty-check.py --review                     # 完整自检报告

每次完成重要任务后，AI 应调用此脚本进行自检。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

LOG_FILE = os.path.expanduser("~/.hermes/profiles/baijie/.honesty-log.json")
PATTERNS_FILE = os.path.expanduser("~/.hermes/profiles/baijie/.honesty-patterns.json")


# ─── 红旗模式（高度怀疑瞎编） ──────────────────────────────────

RED_FLAGS = [
    (r"绝对\S*", "使用了绝对化表述「绝对」"),
    (r"保证\S*", "使用了保证性表述「保证」"),
    (r"100%成功", "使用了 100% 成功保证"),
    (r"肯定\S*", "使用了肯定性表述"),
    (r"万无一失", "使用了绝对化保证"),
]

# ─── 黄旗模式（需要谨慎）───────────────────────────────────────

YELLOW_FLAGS = [
    (r"\d+\.\d+\.\d+", "提到了具体版本号"),
    (r"https?://[^\s]+", "引用了 URL"),
    (r"建议.*执行", "建议执行敏感操作"),
    (r"应该.*可以", "使用了推测性表述"),
    (r"大概.*可能", "使用了模糊推测"),
    (r"一般来说", "以一般性推断代替具体事实"),
    (r"通常.*是", "以通常情况代替实际数据"),
    (r"参数.*是", "在未查证情况下描述参数"),
    (r"配置.*在", "在未确认情况下描述配置路径"),
]

# ─── 禁用词库 ─────────────────────────────────────────────────

FORBIDDEN_PHRASES = [
    "100% 保证",
    "绝对没问题",
    "肯定没 bug",
    "绝对不会出错",
    "绝对不会失败",
    "万无一失",
]


# ─── 工具函数 ─────────────────────────────────────────────────

def load_log() -> dict:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "dont_know_count": 0,
        "self_corrections": 0,
        "red_flag_raises": 0,
        "checks": [],
    }


def save_log(log: dict) -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def check_text(text: str) -> dict:
    """自检一段文字，返回红旗和黄旗列表"""
    red = []
    yellow = []
    forbidden_hits = []

    for pattern, desc in RED_FLAGS:
        if re.search(pattern, text):
            red.append(desc)

    for pattern, desc in YELLOW_FLAGS:
        if re.findall(pattern, text):
            matches = re.findall(pattern, text)
            yellow.append(f"{desc}（匹配: {matches[:3]}）")

    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            forbidden_hits.append(phrase)

    return {
        "red": red,
        "yellow": yellow,
        "forbidden": forbidden_hits,
    }


def format_report(text: str, level: str = "full") -> str:
    """生成自检报告"""
    result = check_text(text)

    if level == "quick":
        if result["red"] or result["forbidden"]:
            return f"⚠️ 自检发现问题：{result['red'] + result['forbidden']}"
        return "✅ 快速自检通过"

    lines = ["## 🔍 诚实自检报告"]

    if not text:
        lines.append("\n📌 未提供检查内容")
        return "\n".join(lines)

    # 红旗
    if result["red"]:
        lines.append("\n🔴 红旗（高度怀疑瞎编）：")
        for item in result["red"]:
            lines.append(f"  - {item}")
    else:
        lines.append("\n✅ 无红旗")

    # 黄旗
    if result["yellow"]:
        lines.append("\n🟡 黄旗（需要谨慎）：")
        for item in result["yellow"]:
            lines.append(f"  - {item}")
    else:
        lines.append("\n✅ 无黄旗")

    # 禁用词
    if result["forbidden"]:
        lines.append("\n🚫 禁用词命中：")
        for item in result["forbidden"]:
            lines.append(f"  - {item}")

    # 综合结论
    total_flags = len(result["red"]) + len(result["forbidden"])
    if total_flags >= 2:
        lines.append("\n⚠️ 建议：回答中存在不确定性，请补充依据或标注前提")
    elif total_flags == 1:
        lines.append("\n🟡 建议：有一处需要核实，请谨慎对待")
    else:
        lines.append("\n✅ 自检通过，诚实度较高")

    return "\n".join(lines)


# ─── 子命令 ───────────────────────────────────────────────────

def cmd_check(args) -> str:
    if not args.input and not args.file:
        return "❌ 请提供 --input 或 --file"
    text = args.input or open(args.file, encoding="utf-8").read()
    return format_report(text, args.level)


def cmd_log_dont_know(args) -> str:
    log = load_log()
    log["dont_know_count"] += 1
    log["checks"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "dont_know",
        "context": args.context or "",
    })
    save_log(log)
    return f"📝 已记录「不知道」时刻（累计 {log['dont_know_count']} 次）"


def cmd_self_correct(args) -> str:
    log = load_log()
    log["self_corrections"] += 1
    log["checks"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "self_correction",
        "original": args.original or "",
        "corrected": args.corrected or "",
    })
    save_log(log)
    return f"📝 已记录自我纠正（累计 {log['self_corrections']} 次）"


def cmd_stats(args) -> str:
    log = load_log()
    total = len(log.get("checks", []))

    lines = ["## 📊 诚实记录统计"]
    lines.append(f"**自检次数**: {total}")
    lines.append(f"**说不知道**: {log['dont_know_count']} 次")
    lines.append(f"**自我纠正**: {log['self_corrections']} 次")
    lines.append(f"**红旗触发**: {log['red_flag_raises']} 次")

    if total > 0:
        dont_know_rate = log['dont_know_count'] / total * 100
        lines.append(f"**不知道率**: {dont_know_rate:.1f}%")

    if log.get("checks"):
        lines.append("\n### 最近 5 条记录")
        for entry in log["checks"][-5:]:
            lines.append(f"- [{entry['time']}] {entry['type']}: {entry.get('context', entry.get('original', ''))[:40]}")

    return "\n".join(lines)


def cmd_review(args) -> str:
    """完整自检报告，AI 主动复盘"""
    log = load_log()

    lines = ["## 🔍 完整诚实自检"]

    # 检查最近回答
    if args.recent:
        lines.append("\n📋 最近回答自检（请对照诚实原则检查）：")
        lines.append("请逐条对照以下原则：")
        lines.append("1. 结论是否有依据？")
        lines.append("2. 版本/命令/参数是否确定？")
        lines.append("3. 有没有「绝对」「保证」「100%」等禁用词？")
        lines.append("4. 有没有未核实就说的配置/路径/数值？")
        lines.append("\n如有违规，请主动纠正并说「我刚才说错了，应该...」")
    else:
        lines.append("\n📌 自检完成")
        lines.append("如有违规，请主动纠正")

    return "\n".join(lines)


# ─── 主入口 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="honesty-check: 诚实自检工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python honesty-check.py --input "这个API绝对没问题，直接调用就行"
  python honesty-check.py --check --input "只需要加一行配置就能解决"
  python honesty-check.py --log-dont-know --context "用户问的是内部接口"
  python honesty-check.py --self-correct --original "应该是这样" --corrected "查了一下，是那样"
  python honesty-check.py --stats
  python honesty-check.py --review
"""
    )

    parser.add_argument("--input", "-i", default="", help="要检查的文字内容")
    parser.add_argument("--file", "-f", default="", help="从文件读取内容检查")
    parser.add_argument("--level", choices=["quick", "full"], default="full", help="检查详细程度")

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="检查文字内容")
    sub.add_parser("log-dont-know", help="记录一次「不知道」")
    sub.add_parser("self-correct", help="记录一次自我纠正")
    sub.add_parser("stats", help="查看统计")
    sub.add_parser("review", help="完整自检报告")

    args = parser.parse_args()

    if not args.cmd:
        # 默认执行检查
        if args.input:
            print(cmd_check(args))
        else:
            print(cmd_review(args))
        return

    try:
        if args.cmd == "check":
            print(cmd_check(args))
        elif args.cmd == "log-dont-know":
            print(cmd_log_dont_know(args))
        elif args.cmd == "self-correct":
            print(cmd_self_correct(args))
        elif args.cmd == "stats":
            print(cmd_stats(args))
        elif args.cmd == "review":
            print(cmd_review(args))
        else:
            parser.print_help()
    except Exception as e:
        print(f"❌ 错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
