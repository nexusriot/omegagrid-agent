from tools.base import BaseTool

class VectorSearchTool(BaseTool):
    name = "vector_search"
    description = "Semantic search in vector memory"

    def __init__(self, vector_store):
        self.vector_store = vector_store

    def run(self, query: str, k: int = 5):
        return {"hits": self.vector_store.search_text(query, k=k)}
