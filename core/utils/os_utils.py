import os

class OsUtils:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 'node_modules'}

    def all_files(self):
        _files = []
        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for file in files:
                full_path = os.path.join(root, file)
                _files.append(full_path)
        return _files

    def tree_structure(self):
        tree_lines = []

        def walk_dir(path, prefix=""):
            try:
                entries = sorted([
                    e for e in os.listdir(path)
                    if e not in self.exclude_dirs
                ])
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                full_path = os.path.join(path, entry)
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                tree_lines.append(f"{prefix}{connector}{entry}")

                if os.path.isdir(full_path):
                    extension = "    " if is_last else "│   "
                    walk_dir(full_path, prefix + extension)

        tree_lines.append(self.base_dir)
        walk_dir(self.base_dir)
        return "\n".join(tree_lines)
