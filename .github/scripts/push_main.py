"""Push the exact generated commit with bounded retries; never rebase its inputs."""
import argparse
import subprocess
import sys
import time


def git(*args):
    result = subprocess.run(['git', *args], text=True, capture_output=True, check=True)
    return result.stdout.strip()


def push(*, attempts=3, delay=2):
    if attempts < 1:
        raise ValueError('At least one push attempt is required')
    for attempt in range(attempts):
        try:
            git('push', 'origin', 'HEAD:refs/heads/main')
        except subprocess.CalledProcessError:
            print(f'Push attempt {attempt + 1}/{attempts} failed', file=sys.stderr)
            if attempt + 1 == attempts:
                raise RuntimeError(f'Push failed after {attempts} attempts') from None
            # A concurrent main update requires regeneration from that revision.
            # Rebasing here would label old outputs with code that did not build them.
            time.sleep(delay)
            continue
        sha = git('rev-parse', 'HEAD')
        remote = git('ls-remote', 'origin', 'refs/heads/main').split()
        if not remote or remote[0] != sha:
            raise RuntimeError('Push completed but remote main does not match the intended commit')
        return sha
    raise AssertionError('Unreachable')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    print(push(attempts=args.attempts))
