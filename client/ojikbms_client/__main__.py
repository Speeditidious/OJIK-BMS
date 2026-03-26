"""OJIK BMS Client CLI entry point."""
import webbrowser

import click
from rich.console import Console
from rich.table import Table

from ojikbms_client import __version__
from ojikbms_client.config import (
    get_api_url,
    load_config,
    set_api_url,
    set_beatoraja_db_dir,
    set_beatoraja_songdata_db_path,
    set_beatoraja_songinfo_db_path,
    set_lr2_db_path,
    set_lr2_song_db_path,
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
def sync() -> None:
    """GUI를 통해 동기화를 실행합니다. (ojikbms-client gui)"""
    console.print("[yellow]CLI 동기화는 지원하지 않습니다. GUI를 사용하세요:[/yellow]")
    console.print("  ojikbms-client gui")


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
    table.add_row("", "")
    table.add_row("[bold]LR2[/bold]", "")
    table.add_row("  기록 DB", cfg.get("lr2_db_path") or "미설정")
    table.add_row("  차분 DB (song.db)", cfg.get("lr2_song_db_path") or "미설정")
    table.add_row("", "")
    table.add_row("[bold]Beatoraja[/bold]", "")
    table.add_row("  기록 DB 폴더", cfg.get("beatoraja_db_dir") or "미설정")
    table.add_row("  차분 DB (songdata.db)", cfg.get("beatoraja_songdata_db_path") or "미설정")
    table.add_row("  차분 정보 DB (songinfo.db)", cfg.get("beatoraja_songinfo_db_path") or "미설정")
    table.add_row("", "")
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
    """Beatoraja 기록 DB 폴더 경로를 설정합니다."""
    set_beatoraja_db_dir(path)
    console.print(f"[green]Beatoraja 기록 DB 폴더 설정됨: {path}[/green]")


@config.command("set-lr2-song")
@click.argument("path")
def config_set_lr2_song(path: str) -> None:
    """LR2 차분 DB(song.db) 경로를 설정합니다."""
    set_lr2_song_db_path(path)
    console.print(f"[green]LR2 차분 DB 경로 설정됨: {path}[/green]")


@config.command("set-beatoraja-songdata")
@click.argument("path")
def config_set_beatoraja_songdata(path: str) -> None:
    """Beatoraja 차분 DB(songdata.db) 경로를 설정합니다."""
    set_beatoraja_songdata_db_path(path)
    console.print(f"[green]Beatoraja 차분 DB 경로 설정됨: {path}[/green]")


@config.command("set-beatoraja-songinfo")
@click.argument("path")
def config_set_beatoraja_songinfo(path: str) -> None:
    """Beatoraja 차분 정보 DB(songinfo.db) 경로를 설정합니다."""
    set_beatoraja_songinfo_db_path(path)
    console.print(f"[green]Beatoraja 차분 정보 DB 경로 설정됨: {path}[/green]")


if __name__ == "__main__":
    cli()
