import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import track
from rich.prompt import Prompt

console = Console()


def backup_workspace(workspace_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_filename = f"{timestamp}-backup.zip"
    backup_path = Path.cwd() / backup_filename

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(workspace_path):
            for file in files:
                filepath = Path(root) / file
                arcname = filepath.relative_to(workspace_path)
                zipf.write(filepath, arcname)

    console.print(f"[green]バックアップ完了: {backup_path}[/green]")
    return backup_path


def find_and_rewrite_links(md_path: Path, workspace_path: Path, attachments_root: Path):
    content = md_path.read_text(encoding="utf-8")
    modified = False

    # Markdown画像リンク等を検出: ![](path) や [](path)
    pattern = re.compile(r"(!?\[.*?\])\(([^)]+)\)")

    def replace_link(match: re.Match[str]) -> str:
        nonlocal modified
        full_match, label, rel_path = match.group(0), match.group(1), match.group(2)

        # 無視するケース
        if rel_path.startswith("http://") or rel_path.startswith("https://"):
            return full_match

        source_path = (md_path.parent / rel_path).resolve()
        if not source_path.exists() or not source_path.is_file():
            return full_match

        relative_md_path = md_path.relative_to(workspace_path).with_suffix(
            ""
        )  # ./path/to/markdown
        new_attachment_dir = attachments_root / relative_md_path
        new_attachment_dir.mkdir(parents=True, exist_ok=True)

        destination_path = new_attachment_dir / source_path.name
        if not destination_path.exists():
            shutil.copy2(source_path, destination_path)
            # delete the original file if it exists
            if source_path.exists():
                source_path.unlink()

        new_rel_path = Path(
            os.path.relpath(destination_path, md_path.parent)
        ).as_posix()
        modified = True
        return f"{label}({new_rel_path})"

    new_content = pattern.sub(replace_link, content)

    if modified:
        md_path.write_text(new_content, encoding="utf-8")
        console.print(f"[cyan]更新: {md_path}[/cyan]")


def process_workspace(workspace_path: Path):
    attachments_root = workspace_path / "attachments"
    md_files = list(workspace_path.rglob("*.md"))

    console.print(f"[bold]Markdownファイル数: {len(md_files)}[/bold]")
    for md_file in track(
        md_files, description="リンク書き換え処理中...", console=console
    ):
        find_and_rewrite_links(md_file, workspace_path, attachments_root)


def main():
    user_input = Prompt.ask(
        "VSCode Note Taking Extensionのワークスペースパスを絶対パスで入力してください"
    )

    # クォートの除去
    if user_input:
        user_input = user_input.strip().strip('"').strip("'")

    if not user_input:
        console.print("[red]パスが入力されていません。[/red]")
        return

    if os.path.isfile(user_input):
        console.print(
            "[red]指定されたパスはファイルです。ディレクトリを指定してください。[/red]"
        )
        return

    if not os.path.exists(user_input):
        console.print(f"[red]指定されたパスが存在しません: {user_input}[/red]")
        return

    workspace_path = Path(user_input).resolve()

    if not workspace_path.is_absolute():
        console.print("[red]絶対パスを指定してください。[/red]")
        return

    if not workspace_path.exists() or not workspace_path.is_dir():
        console.print(
            f"[red]指定されたパスが存在しないか、ディレクトリではありません: {workspace_path}[/red]"
        )
        return

    console.print("[blue]バックアップ中...[/blue]")
    backup_workspace(workspace_path)

    console.print("[blue]リンク修正およびリソースの再配置を開始します...[/blue]")
    process_workspace(workspace_path)
    console.print("[green bold]すべての処理が完了しました。[/green bold]")


if __name__ == "__main__":
    main()
