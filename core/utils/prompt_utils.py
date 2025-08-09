

class PromptUtils:
    @classmethod
    def add_all_files_to_prompt(cls, prompt, all_files):
        for file in all_files:
            with open(file, 'r') as f:
                prompt += "file: " + file + "contains: " + f.read() + "\n\n\n"
        return prompt

    @classmethod
    def add_files_structure_to_prompt(cls, prompt, all_files):
        return prompt + "files structure: " + all_files