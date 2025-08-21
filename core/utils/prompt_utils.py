from core.utils.os_utils import OsUtils
import os

class PromptUtils:
    def __init__(self, selected_folder):
        self.osUtils = OsUtils(selected_folder)

    @classmethod
    def add_all_files_to_prompt(cls, prompt, all_files):
        for file in all_files:
            if os.path.getsize(file) > 1000000:
                prompt += f"\nfile: {file}\ncontains:\n<Skipped large file>\n" + "-" * 50 + "\n"
                continue

            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"<Error reading file: {e}>"

            prompt += f"\nfile: {file}\ncontains:\n{content}\n" + "-" * 50 + "\n"
        return prompt

    @classmethod
    def add_files_structure_to_prompt(cls, prompt, structure_text):
        return prompt + f"\nproject structure:\n{structure_text}\n"

    def final_prompt(self, user_prompt, include_structure=True, include_all_files=True):
        final = ""

        if user_prompt:
            final += f"my question:\n{user_prompt.strip()}\n"

        if include_structure:
            structure_text = self.osUtils.tree_structure()
            final = self.add_files_structure_to_prompt(final, structure_text)

        if include_all_files:
            all_files = self.osUtils.all_files()
            final = self.add_all_files_to_prompt(final, all_files)

        return final
