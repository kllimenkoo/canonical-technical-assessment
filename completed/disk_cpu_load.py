import os
import stat
import argparse
from dataclasses import dataclass
import subprocess


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
    parser = argparse.ArgumentParser(allow_abbrev=False)

    parser.add_argument(
        "--max-load",
        type=int,
        default=30,
        metavar="<load>",
        help=(
            "The maximum acceptable CPU load, as a percentage. Defaults to 30."
        ),
    )
    parser.add_argument(
        "--xfer",
        type=int,
        default=4096,
        metavar="<mebibytes>",
        help=(
            "The amount of data to read from the disk, in mebibytes. "
            "Defaults to 4096 (4 GiB)."
        ),
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
        help=(
            'Whole-disk device path (e.g. "sda" or "/dev/sda"). '
            "Defaults to /dev/sda."
        ),
    )
    args = parser.parse_args()
    args.device_filename = validate_block_device(args.device_filename)

    return args


def get_cpu_stats() -> list[int]:
    """Read and return current CPU statistics from /proc/stat."""
    with open("/proc/stat", "r") as f:
        cpu_line = f.readline()

    return [int(i) for i in cpu_line.split()[1:]]


def read_disk(
    device: str, xfer: int, verbose: bool
) -> tuple[list[int], list[int]]:
    """Flush cache, read disk, return CPU stat snapshots."""
    try:
        subprocess.run(["blockdev", "--flushbufs", device], check=True)
    except subprocess.CalledProcessError:
        raise SystemExit(1)

    if verbose:
        print("Beginning disk read....")

    start_use = get_cpu_stats()
    try:
        subprocess.run(
            [
                "dd",
                f"if={device}",
                "of=/dev/null",
                "bs=1048576",
                f"count={xfer}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        raise SystemExit(1)

    end_use = get_cpu_stats()

    if verbose:
        print("Disk read complete!")

    return start_use, end_use


def compute_cpu_load(
    start_use: list[int], end_use: list[int]
) -> CPULoadResult:
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


def print_result(
    cpu_load_result: CPULoadResult, args: argparse.Namespace
) -> None:
    """Prints the CPU load result."""
    if args.verbose:
        print(f"Start CPU time = {cpu_load_result.start_total}")
        print(f"End CPU time = {cpu_load_result.end_total}")
        print(f"CPU time used = {cpu_load_result.diff_used}")
        print(f"Total elapsed time = {cpu_load_result.diff_total}")

    print(f"Detected disk read CPU load is {cpu_load_result.cpu_load}")


if __name__ == "__main__":
    args = get_params()
    print(
        f"Testing CPU load when reading {args.xfer} MiB "
        f"from {args.device_filename}"
    )
    print(f"Maximum acceptable CPU load is {args.max_load}")

    start_use, end_use = read_disk(
        args.device_filename, args.xfer, args.verbose
    )
    cpu_load_result = compute_cpu_load(start_use, end_use)
    print_result(cpu_load_result, args)

    if cpu_load_result.cpu_load > args.max_load:
        print("*** DISK CPU LOAD TEST HAS FAILED! ***")
        raise SystemExit(1)
