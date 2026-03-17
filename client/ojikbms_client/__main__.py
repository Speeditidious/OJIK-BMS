"""OJIK BMS Client CLI entry point."""
import webbrowser

import click
from rich.console import Console
from rich.table import Table

from ojikbms_client import __version__
from ojikbms_client.config import (
    add_bms_folder,
    get_api_url,
    load_config,
    set_api_url,
    set_beatoraja_db_dir,
    set_lr2_db_path,
)

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="ojikbms-client")
def cli() -> None:
    """OJIK BMS 클라이언트 - BMS 스코어 동기화 도구"""


def _open_browser(url: str) -> bool:
    """Open a URL in the system browser, with WSL2 fallback."""
    import subprocess
    import sys

    # WSL2: use wslview (wslu) or Windows explorer
    if sys.platform == "linux":
        try:
            result = subprocess.run(["wslview", url], capture_output=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            pass
        try:
            subprocess.Popen(
                ["powershell.exe", "-Command", f"Start-Process '{url}'"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            pass

    return webbrowser.open(url)


@cli.command()
def login() -> None:
    """Discord OAuth2 로그인 (브라우저를 열어 인증합니다)."""
    from ojikbms_client.auth import (
        find_free_port,
        get_discord_login_url,
        is_logged_in,
        save_tokens,
        wait_for_oauth_callback,
    )

    if is_logged_in():
        console.print("[green]이미 로그인되어 있습니다.[/green]")
        return

    api_url = get_api_url()
    port = find_free_port()
    login_url = get_discord_login_url(api_url, state=f"agent:{port}")

    console.print("\n[bold]Discord 로그인 URL:[/bold]")
    console.print(f"  [cyan]{login_url}[/cyan]\n")

    opened = _open_browser(login_url)
    if not opened:
        console.print("[yellow]브라우저를 자동으로 열지 못했습니다. 위 URL을 직접 브라우저에서 열어주세요.[/yellow]")

    console.print("[dim]브라우저에서 Discord 로그인을 완료하면 자동으로 인증됩니다... (최대 2분)[/dim]")

    tokens = wait_for_oauth_callback(port, timeout=120)
    if tokens:
        save_tokens(tokens["access_token"], tokens["refresh_token"])
        console.print("[green]로그인 성공![/green]")
    else:
        console.print("[red]로그인 타임아웃. 다시 시도해주세요.[/red]")


@cli.command()
def logout() -> None:
    """로그아웃 (저장된 토큰을 삭제합니다)."""
    from ojikbms_client.auth import clear_tokens

    clear_tokens()
    console.print("[green]로그아웃 완료.[/green]")


@cli.command()
@click.option("--lr2-db", help="LR2 score.db 파일 경로")
@click.option("--beatoraja-dir", help="Beatoraja data 디렉토리 경로")
@click.option("--bms-folder", multiple=True, help="BMS 파일 폴더 경로 (여러 개 가능)")
def sync(
    lr2_db: str | None,
    beatoraja_dir: str | None,
    bms_folder: tuple[str, ...],
) -> None:
    """스코어 및 BMS 파일을 서버와 동기화합니다."""
    from ojikbms_client.auth import is_logged_in
    from ojikbms_client.sync import run_full_sync

    if not is_logged_in():
        console.print("[red]로그인이 필요합니다. `ojikbms-client login` 을 먼저 실행하세요.[/red]")
        return

    config = load_config()

    # Use CLI args if provided, otherwise use config
    lr2_db_path = lr2_db or config.get("lr2_db_path")
    beatoraja_db_dir = beatoraja_dir or config.get("beatoraja_db_dir")
    bms_folders = list(bms_folder) or config.get("bms_folders", [])

    if not lr2_db_path and not beatoraja_db_dir:
        console.print(
            "[yellow]LR2 DB 또는 Beatoraja DB 경로를 설정해주세요.[/yellow]\n"
            "  ojikbms-client config set-lr2 <경로>\n"
            "  ojikbms-client config set-beatoraja <경로>"
        )
        return

    console.print("[bold]OJIK BMS 동기화 시작...[/bold]\n")
    run_full_sync(
        lr2_db_path=lr2_db_path,
        beatoraja_db_dir=beatoraja_db_dir,
        bms_folders=bms_folders,
    )


@cli.command()
@click.argument("folder", required=False)
def scan(folder: str | None) -> None:
    """BMS 폴더를 스캔하여 파일 수와 해시를 확인합니다."""
    from ojikbms_client.parsers.bms_scanner import scan_bms_folders

    config = load_config()
    folders = [folder] if folder else config.get("bms_folders", [])

    if not folders:
        console.print("[yellow]스캔할 폴더가 없습니다. --folder 옵션으로 폴더를 지정하세요.[/yellow]")
        return

    console.print(f"[bold]{len(folders)}개 폴더 스캔 중...[/bold]")
    songs, _ = scan_bms_folders(folders)

    console.print(f"\n[green]스캔 완료:[/green] {len(songs)}개 BMS 파일 발견")


@cli.group()
def config() -> None:
    """설정 관리 명령어"""


@config.command("show")
def config_show() -> None:
    """현재 설정을 표시합니다."""
    cfg = load_config()

    table = Table(title="OJIK BMS 클라이언트 설정")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="green")

    table.add_row("API URL", cfg.get("api_url", ""))
    table.add_row("LR2 DB 경로", cfg.get("lr2_db_path") or "미설정")
    table.add_row("Beatoraja 디렉토리", cfg.get("beatoraja_db_dir") or "미설정")
    table.add_row("BMS 폴더", "\n".join(cfg.get("bms_folders", [])) or "미설정")
    table.add_row("마지막 동기화", cfg.get("last_synced_at") or "없음")

    console.print(table)


@config.command("set-api-url")
@click.argument("url")
def config_set_api_url(url: str) -> None:
    """API 서버 URL을 설정합니다."""
    set_api_url(url)
    console.print(f"[green]API URL 설정됨: {url}[/green]")


@config.command("set-lr2")
@click.argument("path")
def config_set_lr2(path: str) -> None:
    """LR2 score.db 경로를 설정합니다."""
    set_lr2_db_path(path)
    console.print(f"[green]LR2 DB 경로 설정됨: {path}[/green]")


@config.command("set-beatoraja")
@click.argument("path")
def config_set_beatoraja(path: str) -> None:
    """Beatoraja data 디렉토리 경로를 설정합니다."""
    set_beatoraja_db_dir(path)
    console.print(f"[green]Beatoraja 디렉토리 설정됨: {path}[/green]")


@config.command("add-folder")
@click.argument("folder")
def config_add_folder(folder: str) -> None:
    """BMS 파일 폴더를 추가합니다."""
    add_bms_folder(folder)
    console.print(f"[green]폴더 추가됨: {folder}[/green]")


if __name__ == "__main__":
    cli()
