import importlib.metadata
import os


def find_local_distribution(start_dir, entry_point_group=None):
    dir = os.path.abspath(start_dir)
    while True:
        try:
            distributions = importlib.metadata.distributions(path=[dir])
        except (OSError, PermissionError):
            distributions = ()

        for dist in distributions:
            if entry_point_group is None or any(
                ep.group == entry_point_group for ep in dist.entry_points
            ):
                return dist, dir

        parent = os.path.dirname(dir)
        if parent == dir:
            # Top-most directory
            return None, None
        dir = parent
