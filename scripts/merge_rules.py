import os
import re
import shutil
import subprocess
from pathlib import Path


REPO_URL = "https://github.com/blackmatrix7/ios_rule_script.git"
BRANCH = "master"

SOURCE_DIR = Path("_blackmatrix7")
LOON_DIR = SOURCE_DIR / "rule" / "Loon"
OUTPUT_DIR = Path("rules")


def run_command(command: list[str]) -> None:
    print("执行:", " ".join(command))

    result = subprocess.run(
        command,
        check=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"命令执行失败，退出代码: {result.returncode}"
        )


def clone_blackmatrix7() -> None:
    if SOURCE_DIR.exists():
        shutil.rmtree(SOURCE_DIR)

    print("正在拉取 Blackmatrix7 最新仓库...")

    run_command([
        "git",
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--sparse",
        "--branch",
        BRANCH,
        REPO_URL,
        str(SOURCE_DIR),
    ])

    print("正在获取 rule/Loon ...")

    run_command([
        "git",
        "-C",
        str(SOURCE_DIR),
        "sparse-checkout",
        "set",
        "rule/Loon",
    ])

    if not LOON_DIR.exists():
        raise RuntimeError(
            "找不到 Blackmatrix7 的 rule/Loon 目录"
        )


def normalize_domain_rule(line: str) -> str | None:
    """
    Blackmatrix7 的 *_Domain.list 中，
    常见格式：

        .example.com

    转换为：

        DOMAIN-SUFFIX,example.com

    其他规则原样保留。
    """

    line = line.strip()

    if not line:
        return None

    if line.startswith("#"):
        return None

    # Domain 文件里的简写域名
    if (
        line.startswith(".")
        and "," not in line
        and " " not in line
    ):
        domain = line[1:].strip()

        if re.fullmatch(
            r"[A-Za-z0-9*_.-]+",
            domain,
        ):
            return f"DOMAIN-SUFFIX,{domain}"

    return line


def read_rules(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(
            f"规则文件不存在: {path}"
        )

    if not path.is_file():
        raise RuntimeError(
            f"规则路径不是文件: {path}"
        )

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if not text.strip():
        raise RuntimeError(
            f"规则文件为空: {path}"
        )

    return text.splitlines()


def clean_rules(
    lines: list[str],
    convert_domain: bool = False,
) -> list[str]:
    result = []
    seen = set()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if convert_domain:
            normalized = normalize_domain_rule(line)

            if normalized is None:
                continue

            line = normalized

        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result


def find_main_rule(service_dir: Path) -> Path | None:
    """
    优先：
        XXX.list
        XXX.lsr
    """

    service_name = service_dir.name

    for extension in [".list", ".lsr"]:
        path = service_dir / f"{service_name}{extension}"

        if path.is_file():
            return path

    return None


def find_domain_rule(service_dir: Path) -> Path | None:
    """
    优先：
        XXX_Domain.list
        XXX_Domain.lsr
    """

    service_name = service_dir.name

    for extension in [".list", ".lsr"]:
        path = service_dir / f"{service_name}_Domain{extension}"

        if path.is_file():
            return path

    return None


def process_service(service_dir: Path) -> str | None:
    service_name = service_dir.name

    main_file = find_main_rule(service_dir)

    # 没有主规则文件，例如纯 README 目录
    if main_file is None:
        print(
            f"[跳过] {service_name}: "
            f"没有找到主规则文件"
        )
        return None

    print()
    print("=" * 60)
    print(f"[处理] {service_name}")

    main_lines = read_rules(main_file)

    domain_file = find_domain_rule(service_dir)

    domain_lines = []

    if domain_file is not None:
        print(
            f"[合并] {main_file.name} + "
            f"{domain_file.name}"
        )

        domain_lines = read_rules(domain_file)

    else:
        print(
            f"[单文件] {main_file.name}"
        )

    # Domain 规则放前面
    merged = []

    if domain_lines:
        merged.extend(
            clean_rules(
                domain_lines,
                convert_domain=True,
            )
        )

    merged.extend(
        clean_rules(
            main_lines,
            convert_domain=False,
        )
    )

    # 再次统一去重
    final_rules = []
    seen = set()

    for rule in merged:
        if rule in seen:
            continue

        seen.add(rule)
        final_rules.append(rule)

    if not final_rules:
        raise RuntimeError(
            f"{service_name}: 合并结果为空"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        OUTPUT_DIR
        / f"{service_name}.list"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        file.write(
            f"# NAME: {service_name}\n"
        )

        file.write(
            "# SOURCE: "
            "Blackmatrix7 ios_rule_script\n"
        )

        file.write(
            "# FORMAT: Loon merged rule\n"
        )

        file.write(
            f"# TOTAL: {len(final_rules)}\n"
        )

        file.write("#\n")

        for rule in final_rules:
            file.write(rule + "\n")

    print(
        f"[完成] {output_file} "
        f"共 {len(final_rules)} 条"
    )

    return output_file.name


def remove_old_rules(generated_files: set[str]) -> None:
    if not OUTPUT_DIR.exists():
        return

    for path in OUTPUT_DIR.glob("*.list"):
        if path.name not in generated_files:
            print(
                f"[删除] 上游已经不存在: "
                f"{path.name}"
            )
            path.unlink()


def main() -> None:
    print("=" * 60)
    print("Blackmatrix7 Loon 全量同步")
    print("=" * 60)

    clone_blackmatrix7()

    service_dirs = [
        path
        for path in LOON_DIR.iterdir()
        if path.is_dir()
    ]

    service_dirs.sort(
        key=lambda path: path.name.lower()
    )

    if not service_dirs:
        raise RuntimeError(
            "rule/Loon 下没有找到任何规则目录"
        )

    generated_files = set()

    for service_dir in service_dirs:
        result = process_service(
            service_dir
        )

        if result:
            generated_files.add(result)

    remove_old_rules(
        generated_files
    )

    print()
    print("=" * 60)
    print(
        f"同步完成，共生成 "
        f"{len(generated_files)} 个规则文件"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
