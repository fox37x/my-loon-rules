import json
import os
import re
import urllib.request
from urllib.error import HTTPError, URLError


REPO = "blackmatrix7/ios_rule_script"
BRANCH = "master"
LOON_ROOT = "rule/Loon"
OUTPUT_DIR = "rules"

API_URL = (
    f"https://api.github.com/repos/{REPO}/contents/"
    f"{LOON_ROOT}?ref={BRANCH}"
)


def github_request(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "my-loon-rules",
        },
    )

    token = os.environ.get("GITHUB_TOKEN")

    if token:
        request.add_header(
            "Authorization",
            f"Bearer {token}",
        )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            if response.getcode() != 200:
                raise RuntimeError(
                    f"HTTP {response.getcode()}: {url}"
                )

            return json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as exc:
        raise RuntimeError(
            f"GitHub API 请求失败: HTTP {exc.code}\n{url}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"网络请求失败: {exc.reason}\n{url}"
        ) from exc


def download_file(url: str) -> list[str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "my-loon-rules",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            if response.getcode() != 200:
                raise RuntimeError(
                    f"HTTP {response.getcode()}: {url}"
                )

            content = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except HTTPError as exc:
        raise RuntimeError(
            f"规则下载失败: HTTP {exc.code}\n{url}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"规则下载失败: {exc.reason}\n{url}"
        ) from exc

    if not content.strip():
        raise RuntimeError(
            f"规则文件为空:\n{url}"
        )

    return content.splitlines()


def normalize_rule(line: str) -> str | None:
    """
    Blackmatrix7 Loon 的 *_Domain.list 中，
    域名通常使用：

        .example.com

    这里转换成标准 Loon：

        DOMAIN-SUFFIX,example.com
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


def clean_rules(lines: list[str]) -> list[str]:
    result = []
    seen = set()

    for raw_line in lines:
        line = normalize_rule(raw_line)

        if line is None:
            continue

        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result


def find_file(entries: list[dict], filename: str):
    for entry in entries:
        if (
            entry.get("type") == "file"
            and entry.get("name") == filename
        ):
            return entry

    return None


def process_service(service_name: str, entries: list[dict]) -> str | None:
    """
    一个服务最终只生成一个 rules/XXX.list。

    支持：

        XXX.list
        XXX.lsr

    如果存在：

        XXX_Domain.list
        XXX_Domain.lsr

    自动合并。

    XXX_Resolve.list / XXX_Resolve.lsr
    不参与合并。
    """

    main_entry = (
        find_file(entries, f"{service_name}.list")
        or find_file(entries, f"{service_name}.lsr")
    )

    if main_entry is None:
        print(
            f"[跳过] {service_name}: "
            f"没有找到主规则文件"
        )
        return None

    main_lines = download_file(
        main_entry["download_url"]
    )

    domain_entry = (
        find_file(
            entries,
            f"{service_name}_Domain.list",
        )
        or find_file(
            entries,
            f"{service_name}_Domain.lsr",
        )
    )

    domain_lines = []

    if domain_entry is not None:
        print(
            f"[合并] {service_name} + "
            f"{domain_entry['name']}"
        )

        domain_lines = download_file(
            domain_entry["download_url"]
        )

    else:
        print(
            f"[单文件] {service_name}"
        )

    merged = clean_rules(
        domain_lines + main_lines
    )

    if not merged:
        raise RuntimeError(
            f"{service_name}: 合并结果为空"
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{service_name}.list",
    )

    with open(
        output_path,
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
            f"# TOTAL: {len(merged)}\n"
        )
        file.write("#\n")

        for rule in merged:
            file.write(rule + "\n")

    print(
        f"[完成] {service_name}.list "
        f"共 {len(merged)} 条"
    )

    return f"{service_name}.list"


def main():
    print(
        "正在读取 Blackmatrix7 Loon 规则目录..."
    )

    root_entries = github_request(
        API_URL
    )

    service_dirs = [
        entry
        for entry in root_entries
        if entry.get("type") == "dir"
    ]

    if not service_dirs:
        raise RuntimeError(
            "没有找到 Blackmatrix7 Loon 规则目录"
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    generated_files = set()

    for service_entry in sorted(
        service_dirs,
        key=lambda x: x["name"].lower(),
    ):

        service_name = service_entry["name"]

        entries = github_request(
            service_entry["url"]
        )

        result = process_service(
            service_name,
            entries,
        )

        if result:
            generated_files.add(result)

    # 删除已经从 Blackmatrix7 移除的规则
    existing_files = [
        filename
        for filename in os.listdir(
            OUTPUT_DIR
        )
        if filename.endswith(".list")
    ]

    for filename in existing_files:

        if filename not in generated_files:

            path = os.path.join(
                OUTPUT_DIR,
                filename,
            )

            os.remove(path)

            print(
                f"[删除] 上游已经移除: "
                f"{filename}"
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
