import os
import stat
import argparse
from dataclasses import dataclass


@dataclass
class CPULoadResult:
    start_total: int
    end_total: int
    diff_total: int
    diff_used: int
    cpu_load: int


def validate_block_device(path: str) -> str:
    """Validate and normalize block device path."""
    if not path.startswith("/dev/"):
        path = f"/dev/{path}"

    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f'Unknown block device "{path}"')

    file_mode = os.stat(path).st_mode
    if not stat.S_ISBLK(file_mode):
        raise argparse.ArgumentTypeError(f'{path}" is not a block device.')

    return path


def get_params() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--max-load",
        type=int,
        default=30,
        metavar="<load>",
        help="The maximum acceptable CPU load, as a percentage. Defaults to 30.",
    )
    parser.add_argument(
        "--xfer",
        type=int,
        default=4096,
        metavar="<mebibytes>",
        help="The amount of data to read from the disk, in mebibytes. Defaults to 4096 (4 GiB).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="If present, produce more verbose output",
    )
    parser.add_argument(
        "device_filename",
        type=validate_block_device,
        nargs="?",
        default="/dev/sda",
        metavar="device-filename",
        help='Whole-disk device path (e.g. "sda" or "/dev/sda"). Defaults to /dev/sda.',
    )
    args = parser.parse_args()
    args.device_filename = validate_block_device(args.device_filename)

    return args


def compute_cpu_load(start_use: list[int], end_use: list[int]) -> CPULoadResult:
    """Compute CPU load percentage between two /proc/stat snapshots."""
    diff_idle = end_use[3] - start_use[3]

    start_total = sum(start_use)
    end_total = sum(end_use)

    diff_total = end_total - start_total
    diff_used = diff_total - diff_idle

    cpu_load = 0
    if diff_total != 0:
        cpu_load = (diff_used * 100) // diff_total

    return CPULoadResult(
        start_total=start_total,
        end_total=end_total,
        diff_total=diff_total,
        diff_used=diff_used,
        cpu_load=cpu_load,
    )
