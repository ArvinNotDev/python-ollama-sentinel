import os

class OsUtils:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def all_files(self):
        _files = []
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                full_path = os.path.join(root, file)
                _files.append(full_path)
        return _files

