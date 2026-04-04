class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools[name]

    def describe(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]
