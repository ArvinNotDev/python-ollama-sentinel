import ollama

from core.scrapper.web_scrapper import OllamaScrapper


class OllamaUtils:

    @classmethod
    def list_downloaded_models(cls):
        models = []
        try:
            for model in ollama.list()['models']:
                models.append(model)
        except Exception as e:
            print(e)
        return models

    @classmethod
    def list_all_models(cls):
        status, message = OllamaScrapper()()

        if status:
            models_list = OllamaScrapper.list_all_models()
            return models_list
        else:
            print(f"ollama site not reachable: {message}")
            return False

    @classmethod
    def pull_model(cls, model_name: str):
        try:
            print(f"Pulling model: {model_name}...")
            ollama.pull(model_name)
            print(f"Model '{model_name}' downloaded successfully.")
            return True
        except Exception as e:
            print(f"Failed to pull model '{model_name}': {e}")
            return False
