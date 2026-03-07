class BaseTool:
    name = "base"
    description = "base tool"

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description}

    def run(self, **kwargs):
        raise NotImplementedError
