import re
import json
import logging

from homeassistant.helpers import intent
from homeassistant.exceptions import ServiceNotFound
from homeassistant.components import conversation
from homeassistant.components.openai_conversation import OpenAIAgent

_LOGGER = logging.getLogger(__name__)

def parse_response(res):
    p = re.compile(r"(?P<speech>.*)(?P<json>\[.*?\])", re.S | re.M)
    m = p.search(res)
    try:
        return m.group("speech").strip(), json.loads(m.group("json")), None
    except Exception as e:
        return res, [], e

async def async_setup(hass, config):

    original = OpenAIAgent.async_process

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:

        result = await original(self, user_input)
        if result.response.error_code is not None:
            _LOGGER.warning("Error code: {}".format(result.response.error_code))
            return result

        speech, service_calls, error = parse_response(result.response.speech["plain"]["speech"])
        if error is None:
            _LOGGER.debug("speech: {}".format(speech))
            for service_data in service_calls:
                domain, service = service_data.pop("service").split(".", 1)
                _LOGGER.debug("{}.{}: {}".format(domain, service, service_data))
                try:
                    await hass.services.async_call(domain, service, service_data)
                except ServiceNotFound as e:
                    _LOGGER.warning(e)
                except ValueError as e:
                    _LOGGER.warning(e)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(speech)
            return conversation.ConversationResult(
                response=intent_response, conversation_id=result.conversation_id
            )
        else:
            _LOGGER.warning(error)
            return result

    OpenAIAgent.async_process = async_process
    _LOGGER.info("Patched OpenAIAgent.async_process")

    return True
