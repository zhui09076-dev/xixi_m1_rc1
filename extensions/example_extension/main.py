"""示例扩展入口"""

class ExampleExtension:
    """示例扩展：提供一个简单的问候功能"""

    def __init__(self, container):
        self.container = container
        self.name = "示例扩展"

    def greet(self, name: str) -> str:
        return f"示例扩展问候：你好，{name}！"

    def on_enable(self):
        print(f"{self.name} 已启用")

    def on_disable(self):
        print(f"{self.name} 已停用")


def create_extension(container):
    return ExampleExtension(container)
