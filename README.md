# Glean MCP Server

A Model Context Protocol (MCP) server that integrates with Glean's Chat API.

## Prerequisites

* Python 3.10+
* UV package manager (recommended)
* Glean API key with appropriate permissions(/rest/api/v1/*)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/rahul-roy-glean/glean-mcp-server.git
   cd glean-mcp-server
   ```

2. Install dependencies using UV:
   ```
   uv sync
   uv lock
   ```

## Configuration

Before running the server, you need to set up your Glean API credentials. Create a `.env` file in the project root with the following variables:

```
GLEAN_API_KEY=your_api_key_here
GLEAN_BASE_URL=https://your-domain-be.glean.com/rest/api/v1/
```

## Running the Server

### Standalone Mode

To run the server in standalone mode:

```
uv --directory <PATH_TO_CHECKOUT> run glean_server.py
```

### Debug Mode

To debug the server with the MCP inspector:

```
npx @modelcontextprotocol/inspector uv --directory <PATH_TO_CHECKOUT> run glean_server.py
```

You can then test with JSON payloads like:

```json
{
  "messages": [
    {
      "author": "USER",
      "fragments": [
        {
          "text": "What are the company holidays in 2025 ?"
        }
      ],
      "messageType": "CONTENT"
    }
  ],
  "saveChat": true,
  "stream": false
}
```

### Integration with Cursor

To use this server with Cursor, add the following to `~/.cursor/mcp.json`:

```json
{
    "mcpServers": {       
        "glean": {
            "command": "uv",
            "args": [
                "--directory",
                "<PATH_TO_CHECKOUT>",
                "run", "glean_server.py"
            ]
        }
    }
}
```

## Documentation Links

* [Model Context Protocol Documentation](https://modelcontextprotocol.io/introduction)
* [Glean API Documentation](https://developers.glean.com/docs/client_api/chat_api/)
* [MCP GitHub Repository](https://github.com/modelcontextprotocol/docs)
