import unittest

from core.ollama.library import (
    next_search_path,
    parse_model_tags,
    parse_search_results,
)


class OllamaLibraryParserTests(unittest.TestCase):
    def test_parse_multiple_search_cards(self):
        body = """
        <li x-test-model>
          <a href="/library/qwen3" class="group w-full">
            <span x-test-search-response-title>qwen3</span>
            <p class="max-w-lg break-words">Qwen family with multiple sizes.</p>
            <span x-test-pull-count>44.4M</span>
            <span x-test-tag-count>58</span>
            <span x-test-updated>1 year ago</span>
          </a>
        </li>
        <li x-test-model>
          <a href="/library/deepseek-r1" class="group w-full">
            <span x-test-search-response-title>deepseek-r1</span>
            <p class="max-w-lg">Reasoning model.</p>
          </a>
        </li>
        """
        models = parse_search_results(body)
        self.assertEqual([item["name"] for item in models], ["qwen3", "deepseek-r1"])
        self.assertEqual(models[0]["tag_count"], "58")
        self.assertEqual(models[0]["summary"], "Qwen family with multiple sizes.")
        self.assertEqual(models[0]["path"], "/library/qwen3")

    def test_parse_next_search_page(self):
        body = '<button hx-get="/search?page=2&amp;sort=popular"></button>'
        self.assertEqual(next_search_path(body, 1), "/search?page=2&sort=popular")
        self.assertIsNone(next_search_path(body, 2))

    def test_parse_tags_with_size_quant_context_and_latest(self):
        body = """
        <div class="group px-4 py-3">
          <a href="/library/qwen3:latest">qwen3:latest</a>
          <input class="command hidden" value="qwen3:latest" />
          <span class="rounded-full">latest</span>
          <p class="col-span-2 text-neutral-500 text-[13px]">5.2GB</p>
          <p class="col-span-2 text-neutral-500 text-[13px]">40K</p>
          <div class="col-span-2 text-neutral-500 text-[13px] ">Text</div>
          <span class="font-mono text-[11px]">abc123</span>&nbsp;·&nbsp;1 year ago
        </div>
        <div class="group px-4 py-3">
          <a href="/library/qwen3:14b-q4_K_M">qwen3:14b-q4_K_M</a>
          <input class="command hidden" value="qwen3:14b-q4_K_M" />
          <p class="col-span-2 text-neutral-500 text-[13px]">9.3GB</p>
          <p class="col-span-2 text-neutral-500 text-[13px]">40K</p>
          <div class="col-span-2 text-neutral-500 text-[13px] ">Text input</div>
          <span class="font-mono text-[11px]">def456</span>&nbsp;·&nbsp;3 weeks ago
        </div>
        """
        tags = parse_model_tags(body, "qwen3")
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0]["reference"], "qwen3:latest")
        self.assertTrue(tags[0]["latest"])
        self.assertEqual(tags[0]["size"], "5.2GB")
        self.assertEqual(tags[0]["context"], "40K")
        self.assertEqual(tags[1]["tag"], "14b-q4_K_M")
        self.assertEqual(tags[1]["digest"], "def456")

    def test_parse_namespaced_tags(self):
        body = """
        <div class="hidden group px-4 py-3 sm:grid sm:grid-cols-12">
          <a href="/community/qwen3:8b-q4_K_M">community/qwen3:8b-q4_K_M</a>
          <input class="command hidden" value="community/qwen3:8b-q4_K_M" />
        </div>
        """
        tags = parse_model_tags(body, "community/qwen3")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["reference"], "community/qwen3:8b-q4_K_M")


if __name__ == "__main__":
    unittest.main()
