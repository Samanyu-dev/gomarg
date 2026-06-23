from duckduckgo_search import DDGS
import json

def test():
    with DDGS() as ddgs:
        results = [r for r in ddgs.text('site:linkedin.com/in "Product Manager" "Apple"', max_results=5)]
        print(json.dumps(results, indent=2))

test()
