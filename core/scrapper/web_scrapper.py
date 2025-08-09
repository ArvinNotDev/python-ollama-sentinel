from bs4 import BeautifulSoup
import requests
from pydantic import BaseModel
from typing import List, Dict


class ScrapperModel(BaseModel):
    ollama_base_url: str = "https://ollama.com/"
    ollama_library_url: str = ollama_base_url + "library"
    default_header: Dict[str, str] = {"User-Agent": "Mozilla/5.0"}


class OllamaScrapper:

    @classmethod
    def list_all_models(cls) -> List[Dict[str, str]]:
        config = ScrapperModel()

        response = requests.get(config.ollama_library_url, headers=config.default_header)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        model_blocks = soup.find_all("li", class_="flex items-baseline border-b border-neutral-200 py-6")
        models = []

        for block in model_blocks:
            link_tag = block.find("a", href=True)
            summary_tag = block.find("p")

            size_tags = block.find_all("span", class_="inline-flex items-center rounded-md bg-[#ddf4ff] px-2 py-0.5 text-xs font-medium text-blue-600 sm:text-[13px]")
            sizes = [span.text.strip() for span in size_tags]
            model_sizes = ", ".join(sizes) if sizes else "N/A"

            if link_tag and 'href' in link_tag.attrs:
                full_link = f"https://ollama.com{link_tag['href']}"
                model_name = link_tag['href'].rstrip('/').split('/')[-1]
            else:
                continue

            summary = summary_tag.text.strip() if summary_tag else "N/A"

            models.append({
                "name": model_name,
                "link": full_link,
                "summary": summary,
                "sizes": model_sizes
            })

        return models

    def __call__(self, *args, **kwargs):
        config = ScrapperModel()
        try:
            response = requests.get(config.ollama_base_url, headers=config.default_header, timeout=5)
            response.raise_for_status()
            return True, "success"
        except requests.RequestException as e:
            return False, str(e)