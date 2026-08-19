import logfire
from nemoguardrails import LLMRails, RailsConfig
from app.guardrails.service import initialize_rails, guard, rails_app
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

initialize_rails()

# Enable debug logging for NeMo Guardrails
import logging
logging.getLogger("nemoguardrails").setLevel(logging.DEBUG)

print("Testing coffee...")
res, content = guard("how to make coffee")
print("Guard result:", res, content)
