import ollama

from core.scrapper.web_scrapper import OllamaScrapper


class OllamaUtils:

    @classmethod
    def list_downloaded_models(cls):
        try:
            models = ollama.list()
            for model in models['models']:
                yield model
        except:
            pass

    @classmethod
    def list_all_models(cls):
        status, message = OllamaScrapper()()

        if status:
            models_list = OllamaScrapper.list_all_models()
            return models_list
        else:
            print(f"ollama site not reachable: {message}")
            return False

print(OllamaUtils.list_all_models())