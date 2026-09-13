import httpx
from loguru import logger

class EmbeddingProvider:
    def __init__(self, api_key="", api_base="", model="embedding-2"):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model

    async def embed(self, text: str) -> list[float]:
        url = f"{self.api_base}/embeddings"
        body={"model":self.model, "input": text}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            logger.error("embedding 失败: {}{}", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        return data["data"][0]["embedding"]