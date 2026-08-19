from nemoguardrails.llm import LLMModel, LLMResponse
from app.services.llm import get_llm
import asyncio

class PortkeyLLMModel(LLMModel):
    def __init__(self):
        super().__init__()
        self.llm = get_llm()

    async def generate_async(self, prompt: str, **kwargs) -> LLMResponse:
        res = await self.llm.ainvoke(prompt)
        return LLMResponse(content=res.content)
        
    async def generate_events_async(self, *args, **kwargs):
        pass

async def main():
    model = PortkeyLLMModel()
    res = await model.generate_async("Say hello")
    print("Response:", res.content)

asyncio.run(main())
