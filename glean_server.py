"""MCP server for Glean Chat and Search APIs."""

import json
import logging
import os
import sys
from typing import Annotated, List, Optional, Dict

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import (
    ErrorData,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

load_dotenv()

GLEAN_API_KEY = os.getenv("GLEAN_API_KEY")
GLEAN_BASE_URL = os.getenv("GLEAN_BASE_URL", "https://scio-prod-be.glean.com/rest/api/v1/")


class Fragment(BaseModel):
    """A text fragment in a message."""
    text: str


class ChatMessage(BaseModel):
    """A chat message in the conversation."""
    author: str = "USER"
    fragments: List[Fragment]
    messageType: str = "CONTENT"


class ChatRequest(BaseModel):
    """Parameters for making a chat request."""
    messages: Annotated[List[ChatMessage], Field(description="List of messages in the conversation")]
    saveChat: bool
    stream: bool


class GleanAPIError(Exception):
    """Exception raised for Glean API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


def parse_response(json_data):
    all_fragments_text = []
    logger.info(f"Parsing response from Glean API with size {len(json_data)}")
    for message in json_data:
        logger.info(f"Processing {message}")
        try:
            # Check if the data contains messages
            if 'fragments' in message:
                for fragment in message['fragments']:
                    # Check if the fragment contains text
                    if 'text' in fragment:
                        all_fragments_text.append(fragment['text'])

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            continue

    logger.info(f"All fragments: {all_fragments_text}")
    return all_fragments_text


async def make_glean_request(endpoint: str, method: str = "POST", data: Optional[Dict] = None) -> Dict:
    """Make a request to the Glean API."""
    if not GLEAN_API_KEY:
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message="GLEAN_API_KEY environment variable is not set",
        ))

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method,
                f"{GLEAN_BASE_URL}/{endpoint}",
                headers={
                    "Authorization": f"Bearer {GLEAN_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=data,
                timeout=300.0
            )

            if response.status_code == 401:
                raise GleanAPIError("Invalid Glean API key", status_code=401)
            elif response.status_code == 403:
                raise GleanAPIError("Access forbidden - check API key permissions", status_code=403)
            elif response.status_code == 429:
                raise GleanAPIError("Rate limit exceeded", status_code=429)

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message="Request to Glean API timed out",
            ))
        except httpx.RequestError as e:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to connect to Glean API: {str(e)}",
            ))
        except GleanAPIError as e:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=e.message,
            ))
        except httpx.HTTPStatusError as e:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message=f"Glean API error: {str(e)}",
            ))


# Create the FastMCP instance
logger.info("Starting Glean MCP server...")
mcp = FastMCP("mcp-glean")


@mcp.tool()
async def chat(messages: List[ChatMessage]) -> str:
    """Send a chat request to Glean's Chat API."""
    try:
        # Validate the input parameters
        args = ChatRequest(messages=messages, saveChat=True, stream=False)
    except ValueError as e:
        raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e)))

    try:
        request_data = {
            "messages": [message.dict() for message in messages],
            "saveChat": True,
            "stream": False
        }

        # Make the API request
        response = await make_glean_request(
            "chat",
            method="POST",
            data=request_data,
        )

        # Check if the response contains the expected fields
        if not response:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR,
                message="Empty response received from Glean Chat API",
            ))

        # Extract the assistant's response from the API response
        if "messages" in response and isinstance(response["messages"], list):
            # Find the last assistant message in the response
            assistant_messages = [msg for msg in response["messages"]
                                  if isinstance(msg, dict) and
                                  msg.get("author") == "GLEAN_AI"]

            if assistant_messages:
                # Get the last assistant message
                last_message = assistant_messages[-1]
                logger.info(f"Last assistant message parsed")

                # Extract text from fragments
                return "\n---\n".join(parse_response(assistant_messages))

        # If we can't find an assistant message in the expected format,
        # check for alternative response formats
        if "content" in response and isinstance(response["content"], str):
            return response["content"]

        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message="Could not extract assistant response from Glean Chat API",
        ))

    except McpError:
        raise
    except Exception as e:
        logger.error(f"Error in chat function: {str(e)}", exc_info=True)
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"Error processing chat request: {str(e)}",
        ))


if __name__ == "__main__":
    # Initialize and run the server
    logger.info("Starting Glean MCP server with stdio transport")
    try:
        # Use a synchronous initialization to ensure the server is ready
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Error starting MCP server: {str(e)}", exc_info=True)
        sys.exit(1)
