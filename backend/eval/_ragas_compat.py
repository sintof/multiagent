"""
ragas (0.2.x/0.4.x) unconditionally imports ChatVertexAI from
langchain_community.chat_models.vertexai at load time — purely to list it in an
isinstance() feature-check (ragas/llms/base.py: MULTIPLE_COMPLETION_SUPPORTED). That
submodule no longer exists in current langchain-community (sunset in favor of the
standalone langchain-google-vertexai package), so `import ragas` fails outright even
though we never use VertexAI. A dummy stub class is safe here since it's never
instantiated — just needs to exist as an importable name.

Must be imported before anything imports `ragas`.
"""

import sys
import types

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _shim = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # stub — never instantiated, only referenced in an isinstance list
        pass

    _shim.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _shim
