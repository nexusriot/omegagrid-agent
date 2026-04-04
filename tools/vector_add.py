from tools.base import BaseTool

class VectorAddTool(BaseTool):
    name = "vector_add"
    description = "Store durable memory in vector store"

    def __init__(self, vector_store):
        self.vector_store = vector_store

    def run(self, text: str, meta: dict | None = None):
        return self.vector_store.add_text(text, meta or {})
