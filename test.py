import os
from crewai import LLM
class SafeLLM(LLM):
    def call(self, messages, *args, **kwargs):
        for m in messages: m.pop('cache_breakpoint', None)
        return super().call(messages, *args, **kwargs)
llm = SafeLLM(model='groq/openai/gpt-oss-120b')
print(llm.call(messages=[{'role': 'system', 'content': 'hi', 'cache_breakpoint': True}]))
