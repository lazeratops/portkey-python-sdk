from __future__ import annotations
from portkey_ai import Portkey
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    TypedDict,
    Union,
    cast,
)

try:
    from langchain.callbacks.manager import CallbackManagerForLLMRun
    from langchain.chat_models.base import SimpleChatModel
    from langchain.pydantic_v1 import Field, PrivateAttr
    from langchain.schema.messages import (
        AIMessage,
        AIMessageChunk,
        BaseMessage,
        ChatMessage,
        FunctionMessage,
        HumanMessage,
        SystemMessage,
    )
    from langchain.schema.output import (
        ChatGenerationChunk,
    )
except ImportError as exc:
    raise Exception(
        "Langchain is not installed.Please install it with `pip install langchain`."
    ) from exc


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


IMPORT_ERROR_MESSAGE = (
    "Portkey is not installed.Please install it with `pip install portkey-ai`."
)


def convert_message_to_dict(message: BaseMessage) -> dict:
    message_dict: Dict[str, Any]
    if isinstance(message, ChatMessage):
        message_dict = {"role": message.role, "content": message.content}
    elif isinstance(message, HumanMessage):
        message_dict = {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        message_dict = {"role": "assistant", "content": message.content}
        if "function_call" in message.additional_kwargs:
            message_dict["function_call"] = message.additional_kwargs["function_call"]
            # If function call only, content is None not empty string
            if message_dict["content"] == "":
                message_dict["content"] = None
    elif isinstance(message, SystemMessage):
        message_dict = {"role": "system", "content": message.content}
    elif isinstance(message, FunctionMessage):
        message_dict = {
            "role": "function",
            "content": message.content,
            "name": message.name,
        }
    else:
        raise TypeError(f"Got unknown type {message}")
    if "name" in message.additional_kwargs:
        message_dict["name"] = message.additional_kwargs["name"]
    return message_dict


class Message(TypedDict):
    role: str
    content: str


class ChatPortkey(SimpleChatModel):
    """`Portkey` Chat large language models.
    To use, you should have the ``portkey-ai`` python package installed, and the
    environment variable ``PORTKEY_API_KEY``, set with your API key, or pass
    it as a named parameter to the `Portkey` constructor.
    NOTE: You can install portkey using ``pip install portkey-ai``
    Example:
        .. code-block:: python
            import portkey
            from langchain.chat_models import ChatPortkey
            # Simplest invocation for an openai provider. Can be extended to
            # others as well
            llm_option = portkey.LLMOptions(
                provider="openai",
                # Checkout the docs for the virtual-api-key
                virtual_key="openai-virtual-key",
                model="text-davinci-003"
            )
            # Initialise the client
            client = ChatPortkey(
                api_key="PORTKEY_API_KEY",
                mode="single"
            ).add_llms(llm_params=llm_option)
            response = client("What are the biggest risks facing humanity?")
    """

    model: Optional[str] = Field(default="gpt-3.5-turbo")

    _client: Any = PrivateAttr()
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    virtual_key: Optional[str] = None
    config: Optional[Union[Mapping, str]] = None
    provider: Optional[str] = None
    trace_id: Optional[str] = None
    custom_metadata: Optional[str] = None
    streaming: bool = False

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        virtual_key: Optional[str] = None,
        config: Optional[Union[Mapping, str]] = None,
        provider: Optional[str] = None,
        trace_id: Optional[str] = None,
        custom_metadata: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__()

        self._client = Portkey(
            api_key=api_key,
            base_url=base_url,
            virtual_key=virtual_key,
            config=config,
            provider=provider,
            trace_id=trace_id,
            metadata=custom_metadata,
            **kwargs,
        )
        self.model = None

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call Portkey's chatCompletions endpoint.
        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            The string generated by the provider set in the initialisation of the LLM.
        Example:
            .. code-block:: python
                message = [{
                    "role": "user",
                    "content": "Tell me a joke."
                }]
                response = portkey(message)
        """
        _messages = cast(Message, self._create_message_dicts(messages))
        response = self._client.chat.completions.create(
            messages=_messages, stream=False, stop=stop, **kwargs
        )
        message = response.choices[0].message
        return message.content if message else ""

    def _create_message_dicts(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, Any]]:
        message_dicts = [convert_message_to_dict(m) for m in messages]
        return message_dicts

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Call Portkey completion_stream and return the resulting generator.
        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            A generator representing the stream of tokens from Portkey.
        Example:
            .. code-block:: python
                prompt = "Write a poem about a stream."
                generator = portkey.stream(prompt)
                for token in generator:
                    yield token
        """
        _messages = cast(Message, self._create_message_dicts(messages))
        response = self._client.chat.completions.create(
            messages=_messages, stream=True, stop=stop, **kwargs
        )
        for token in response:
            _content = token.choices[0].delta.get("content") or ""
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=_content))
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "portkey-ai-gateway"
