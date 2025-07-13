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

MESSAGES = {
    "choose_language": {
        "ja": "言語を選択してください（ja または en）",
        "en": "Please select a language (ja or en)",
    },
    "enter_path": {
        "ja": "VSCode Note Taking Extensionワークスペースの絶対パスを入力してください",
        "en": "Enter the absolute path to your VSCode Note Taking Extension workspace",
    },
    "no_input": {"ja": "パスが入力されていません。", "en": "No path was entered."},
    "file_not_directory": {
        "ja": "指定されたパスはファイルです。ディレクトリを指定してください。",
        "en": "The specified path is a file. Please provide a directory.",
    },
    "path_not_exist": {
        "ja": "指定されたパスが存在しません: {}",
        "en": "The specified path does not exist: {}",
    },
    "not_absolute_path": {
        "ja": "絶対パスを指定してください。",
        "en": "Please provide an absolute path.",
    },
    "not_directory": {
        "ja": "指定されたパスが存在しないか、ディレクトリではありません: {}",
        "en": "The specified path does not exist or is not a directory: {}",
    },
    "backup_start": {"ja": "バックアップ中...", "en": "Backing up..."},
    "backup_done": {"ja": "バックアップ完了: {}", "en": "Backup completed: {}"},
    "processing_start": {
        "ja": "リンク修正およびリソースの再配置を開始します...",
        "en": "Starting link rewriting and resource relocation...",
    },
    "markdown_count": {
        "ja": "Markdownファイル数: {}",
        "en": "Number of Markdown files: {}",
    },
    "updating": {"ja": "更新: {}", "en": "Updated: {}"},
    "done": {"ja": "すべての処理が完了しました。", "en": "All processing is complete."},
    "processing_links": {"ja": "リンク書き換え処理中...", "en": "Rewriting links..."},
    "moving_resource": {
        "ja": "リソースを移動中: {}\n               -> {}",
        "en": "Moving resource: {}\n              -> {}",
    },
    "rename_vscode_conf_dir": {
        "ja": ".vscodeディレクトリをバックアップしています: {}",
        "en": "Backing up .vscode directory: {}",
    },
}


def get_message(key: str, lang: str, *args):
    return MESSAGES[key][lang].format(*args)


def backup_workspace(workspace_path: Path, lang: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_filename = f"{timestamp}-backup.zip"
    backup_path = Path.cwd() / backup_filename

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(workspace_path):
            for file in files:
                filepath = Path(root) / file
                arcname = filepath.relative_to(workspace_path)
                zipf.write(filepath, arcname)

    console.print(f"[green]{get_message('backup_done', lang, backup_path)}[/green]")
    return backup_path


def find_and_rewrite_links(
    md_path: Path, workspace_path: Path, attachments_root: Path, lang: str
):
    content = md_path.read_text(encoding="utf-8")
    modified = False

    pattern = re.compile(r"(!?\[.*?\])\(([^)]+)\)")

    def replace_link(match: re.Match[str]) -> str:
        nonlocal modified
        label, rel_path = match.group(1), match.group(2)

        if rel_path.startswith("http://") or rel_path.startswith("https://"):
            return match.group(0)

        source_path = (md_path.parent / rel_path).resolve()
        if not source_path.exists() or not source_path.is_file():
            return match.group(0)

        relative_md_path = md_path.relative_to(workspace_path).with_suffix("")
        new_attachment_dir = attachments_root / relative_md_path
        new_attachment_dir.mkdir(parents=True, exist_ok=True)

        destination_path = new_attachment_dir / source_path.name
        if not destination_path.exists():
            shutil.copy2(source_path, destination_path)
            console.print(
                f"[white]{get_message('moving_resource', lang, source_path, destination_path)}[/white]"
            )
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
        console.print(f"[cyan]{get_message('updating', lang, md_path)}[/cyan]")


def process_workspace(workspace_path: Path, lang: str):
    attachments_root = workspace_path / "attachments"
    md_files = list(workspace_path.rglob("*.md"))

    console.print(f"[bold]{get_message('markdown_count', lang, len(md_files))}[/bold]")
    for md_file in track(
        md_files, description=get_message("processing_links", lang), console=console
    ):
        find_and_rewrite_links(md_file, workspace_path, attachments_root, lang)


def main():
    lang = Prompt.ask(get_message("choose_language", "en")).lower()
    if lang not in ("ja", "en"):
        lang = "en"

    user_input = Prompt.ask(get_message("enter_path", lang))

    if user_input:
        user_input = user_input.strip().strip('"').strip("'")

    if not user_input:
        console.print(f"[red]{get_message('no_input', lang)}[/red]")
        return

    if os.path.isfile(user_input):
        console.print(f"[red]{get_message('file_not_directory', lang)}[/red]")
        return

    if not os.path.exists(user_input):
        console.print(f"[red]{get_message('path_not_exist', lang, user_input)}[/red]")
        return

    workspace_path = Path(user_input).resolve()

    if not workspace_path.is_absolute():
        console.print(f"[red]{get_message('not_absolute_path', lang)}[/red]")
        return

    if not workspace_path.exists() or not workspace_path.is_dir():
        console.print(
            f"[red]{get_message('not_directory', lang, workspace_path)}[/red]"
        )
        return

    console.print(f"[blue]{get_message('backup_start', lang)}[/blue]")
    backup_workspace(workspace_path, lang)

    # if .vscode exists, rename it to .vscode_backup
    vscode_path = workspace_path / ".vscode"
    if vscode_path.exists() and vscode_path.is_dir():
        backup_vscode_path = workspace_path / ".vscode_backup"
        if backup_vscode_path.exists():
            shutil.rmtree(backup_vscode_path)
        shutil.move(vscode_path, backup_vscode_path)
        console.print(
            f"[yellow]{get_message('rename_vscode_conf_dir', lang, vscode_path)}[/yellow]"
        )

    console.print(f"[blue]{get_message('processing_start', lang)}[/blue]")
    process_workspace(workspace_path, lang)
    console.print(f"[green bold]{get_message('done', lang)}[/green bold]")


if __name__ == "__main__":
    main()
