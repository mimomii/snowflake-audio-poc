from pathlib import Path

from mutagen import File as MutagenFile

MAX_SIZE_BYTES = 700 * 1024 * 1024       # 700 MB
MAX_DURATION_DEFAULT_SEC = 120 * 60      # 120 分
MAX_DURATION_WORD_SPEAKER_SEC = 60 * 60  # 60 分（word / speaker モード）

TOKENS_PER_SEC = 50
MIN_BILLING_SEC = 10
COST_PER_HOUR_USD = 0.35


def get_audio_info(file_path: str) -> dict:
    path = Path(file_path)
    size_bytes = path.stat().st_size

    audio = MutagenFile(file_path)
    duration_sec = audio.info.length if audio else None

    return {
        "file_name": path.name,
        "size_bytes": size_bytes,
        "duration_sec": duration_sec,
    }


def check_constraints(file_path: str, mode: str = "default") -> list[str]:
    info = get_audio_info(file_path)
    warnings = []

    if info["size_bytes"] > MAX_SIZE_BYTES:
        mb = info["size_bytes"] / 1024 / 1024
        warnings.append(f"ファイルサイズ上限超過: {mb:.1f} MB > 700 MB")

    max_dur = MAX_DURATION_WORD_SPEAKER_SEC if mode in ("word", "speaker") else MAX_DURATION_DEFAULT_SEC
    if info["duration_sec"] and info["duration_sec"] > max_dur:
        mins = info["duration_sec"] / 60
        warnings.append(f"再生時間上限超過: {mins:.1f} 分 > {max_dur // 60} 分")

    return warnings


def estimate_cost(durations_sec: list[float]) -> dict:
    total_effective_sec = sum(max(d, MIN_BILLING_SEC) for d in durations_sec)
    total_tokens = int(total_effective_sec * TOKENS_PER_SEC)
    estimated_cost_usd = (total_effective_sec / 3600) * COST_PER_HOUR_USD
    return {
        "total_effective_sec": total_effective_sec,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def format_duration(sec: float) -> str:
    if sec is None:
        return "不明"
    m, s = divmod(int(sec), 60)
    return f"{m}分{s:02d}秒"
