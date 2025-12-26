#!/usr/bin/env python3
import subprocess
import os
import sys

def run_command(command, description):
    print(f"\n[🚀] {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description}完成。")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败。")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"ℹ️ 未找到执行命令，跳过 {description}。")
        return True

def main():
    print("="*60)
    print("GitBook Downloader 本地安全与环境审核工具")
    print("="*60)

    # 1. 检查依赖
    run_command("pip install -r requirements.txt", "更新 Python 依赖")

    # 2. 代码规范检查
    run_command("flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics", "代码规范运行检查 (Flake8)")

    # 3. 单元测试
    run_command("pytest", "运行单元测试 (Pytest)")

    print("\n✨ 审核流程结束。")

if __name__ == "__main__":
    main()
