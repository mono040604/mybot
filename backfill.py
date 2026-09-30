import asyncio
import json
from pathlib import Path
from providers.embedding import EmbeddingProvider
import storage.wordbook_store as store

cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
oc = cfg["providers"]["openai"]
embedder = EmbeddingProvider(
    api_key=oc["api_key"], api_base=oc["api_base"],model="embedding-2" 
)

async def main():
    words = store.get_words_without_embedding()

    for w in words:
        vector = await embedder.embed(f"{w['cn_text']} {w['kor_text']}")
        if vector:
            store.update_word_embedding(w["word_id"], vector)
    print(f"完成，共 {len(words)} 个词") 

asyncio.run(main())