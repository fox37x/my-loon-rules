import os
import urllib.request
from urllib.error import HTTPError, URLError

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "blackmatrix7/ios_rule_script/master/rule/Loon"
)

# 需要生成的规则
SERVICES = [
    "Tencent",
    "Alibaba",
    "Apple",
    "OpenAI",
    "Telegram",
    "Google",
    "YouTube",
    "GitHub",
    "Twitter",
    "Spotify",
    "Discord",
    "Facebook",
    "Instagram",
    "Steam",
    "TikTok",
    "Amazon",
    "Reddit",
    "Claude",
    "Gemini",
    "YouTubeMusic",
    "GoogleDrive",
]

OUTPUT_DIR = "rules"


def fetch_file(url: str) -> tuple[bool, list[str]]:
    """
    下载规则文件。

    返回：
        (True, 内容)
        (False, [])
    """
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.getcode()

            if status != 200:
                print(f"HTTP 状态异常: {status} -> {url}")
                return False, []

            content = response.read().decode(
                "utf-8",
                errors="replace"
            )

            lines = content.splitlines()

            if not lines:
                print(f"文件为空: {url}")
                return False, []

            return True, lines

    except HTTPError as e:
        print(f"HTTP 错误 {e.code}: {url}")
        return False, []

    except URLError as e:
        print(f"网络错误: {e.reason}: {url}")
        return False, []

    except Exception as e:
        print(f"未知错误: {e}: {url}")
        return False, []


def clean_rules(lines: list[str]) -> list[str]:
    """
    清理规则：
    1. 删除空行
    2. 删除注释
    3. 保留真正的 Loon 规则
    4. 按原始内容去重
    """
    result = []
    seen = set()

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result


def merge_service(service: str) -> None:
    print("=" * 60)
    print(f"处理: {service}")

    service_url = f"{BASE_URL}/{service}"

    main_url = f"{service_url}/{service}.list"
    domain_url = f"{service_url}/{service}_Domain.list"

    # 主文件必须存在
    main_ok, main_lines = fetch_file(main_url)

    if not main_ok:
        raise RuntimeError(
            f"{service}.list 下载失败，停止更新，防止生成残缺规则。"
        )

    # Domain 文件属于可选文件
    domain_ok, domain_lines = fetch_file(domain_url)

    if domain_ok:
        print(f"发现 {service}_Domain.list，开始合并")
    else:
        print(f"没有找到 {service}_Domain.list，只使用 {service}.list")

    # Domain 放前面，主文件放后面
    merged = clean_rules(domain_lines + main_lines)

    if not merged:
        raise RuntimeError(
            f"{service} 合并后的规则为空，停止更新。"
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{service}.list"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        f.write(
            f"# NAME: {service}\n"
            f"# SOURCE: Blackmatrix7 ios_rule_script\n"
            f"# FORMAT: Loon merged rule\n"
            f"# TOTAL: {len(merged)}\n"
            f"#\n"
        )

        for rule in merged:
            f.write(rule + "\n")

    print(
        f"完成: {output_path} "
        f"共 {len(merged)} 条规则"
    )


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for service in SERVICES:
        merge_service(service)

    print()
    print("=" * 60)
    print("全部规则处理完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
