# Sakura Rasa Inference Server

FastAPI inference server for AI-based virtual try-on image generation with modular AI provider support, Django backend integration, comprehensive logging, and robust error handling.

## Features

- **Modular AI Provider Support**: Easy switching between OpenAI, Sora, Gemini, Stability AI, etc.
- **Django Backend Integration**: Authentication, credit checking, and webhook updates
- **Comprehensive Logging**: Request/response logging with latency tracking
- **Error Handling**: Robust error handling with proper HTTP status codes
- **Async I/O**: High-performance async operations with aiohttp
- **Production Ready**: Environment-based configuration, retry logic, and monitoring

## Project Structure

```
inference/
├─ main.py                 # FastAPI app entry point
├─ routers/
│   ├─ __init__.py
│   └─ generate.py         # /api/v1/create-image endpoint
├─ services/
│   ├─ __init__.py
│   ├─ ai_provider.py      # Modular AI provider interface
│   └─ logger.py           # Request/response logging
├─ utils/
│   ├─ __init__.py
│   └─ http_client.py      # Async HTTP client for Django backend
├─ .env                    # Environment variables
├─ requirements.txt        # Python dependencies
├─ .gitignore              # Git ignore rules
├─ README.md               # This file
├─ logs/                   # Log directory (created at runtime)
└─ media/                  # Generated images directory (created at runtime)
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Django Backend Configuration
BACKEND_URL=http://localhost:8000

# AI Provider Configuration
AI_PROVIDER=gemini  # Options: openai, gemini, sora, stability
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_PROJECT_ID=your_google_project_id
GOOGLE_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Service Configuration
SERVICE_NAME=sakura-rasa-inference
LOG_LEVEL=INFO
THROTTLE_RPM=10  # Requests per minute per user

# Server Configuration
PORT=8001
```

### 3. Run the Server

```bash
uvicorn main:app --reload --port 8001
```

Or using Python:

```bash
python main.py
```

The server will start on `http://localhost:8001`

## API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## API Endpoints

### POST `/api/v1/create-image`

Generate a virtual try-on image.

**Request Body:**
```json
{
  "user_id": "string",
  "api_key": "string",
  "catalog_id": "string",
  "user_image_url": "https://example.com/user.jpg",
  "catalog_image_url": "https://example.com/catalog.jpg"
}
```

**Response:**
```json
{
  "status": "success",
  "image_url": "/media/user123_catalog456_1234567890.png",
  "latency_ms": 1234.56
}
```

**Error Responses:**
- `401 Unauthorized`: Authentication failed
- `403 Forbidden`: Insufficient credits
- `500 Internal Server Error`: Server error

### GET `/`

Root endpoint - service information.

### GET `/health`

Health check endpoint.

## Flow

1. **Authentication**: Validates user and API key via Django backend `/api/v1/auth/verify/`
2. **Credit Check**: Checks available credits via Django backend `/api/v1/credits/check/`
3. **Image Generation**: Generates image using configured AI provider
4. **Image Storage**: Saves generated image to `media/` directory
5. **Webhook Update**: Sends usage stats to Django backend `/api/v1/inference/webhook/`
6. **Response**: Returns image URL and latency metrics

## AI Providers

### OpenAI

Implemented using OpenAI DALL-E 3 API. Set `AI_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`.

### Google Gemini

Implemented using Google Gemini 1.5 Pro for image analysis and Imagen API for image generation. 

**Setup:**
1. Set `AI_PROVIDER=gemini` in `.env`
2. Set `GOOGLE_API_KEY` (Gemini API key)
3. Set `GOOGLE_PROJECT_ID` (Google Cloud project ID)
4. Set `GOOGLE_LOCATION` (default: `us-central1`)
5. Optionally set `GOOGLE_APPLICATION_CREDENTIALS` for service account authentication

**Prompt:** Uses optimized prompt for virtual try-on: "take the person from the first reference image and the garment and the setting from the second image, virtual try on should match the model's body. catalogue shoot. 4k. photorealistic. new shot and visual. three quarter angle shot"

### Adding New Providers

To add a new AI provider:

1. Create a new provider class in `services/ai_provider.py` extending `AIProvider`
2. Implement the `generate_image()` method
3. Add the provider to the `providers` dictionary in `get_ai_provider()`
4. Set `AI_PROVIDER` environment variable to your provider name

Example:
```python
class MyProvider(AIProvider):
    async def generate_image(self, user_img_url: str, catalog_img_url: str, prompt: Optional[str] = None) -> str:
        # Your implementation
        pass
```

## Logging

Logs are written to `logs/inference.log` with the following information:
- User ID
- Catalog ID
- Status (success/error)
- Latency (ms)
- AI Provider
- Errors (if any)

Logs are rotated when they reach 10MB, keeping 5 backup files.

## Error Handling

The server implements comprehensive error handling:
- **Network Errors**: Retry logic with exponential backoff
- **Authentication Errors**: 401 Unauthorized
- **Credit Errors**: 403 Forbidden
- **Rate Limiting**: 429 Too Many Requests (configurable via `THROTTLE_RPM`)
- **Server Errors**: 500 Internal Server Error with detailed messages

All errors are logged and returned in a consistent format:
```json
{
  "detail": "Error message"
}
```

## Throttling

Rate limiting is enabled by default (10 requests per minute per user). Configure via `THROTTLE_RPM` environment variable. Throttling is based on user ID or IP address.

## Testing

### Using cURL

```bash
curl -X POST "http://localhost:8001/api/v1/create-image" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "api_key": "your_api_key",
    "catalog_id": "catalog456",
    "user_image_url": "https://example.com/user.jpg",
    "catalog_image_url": "https://example.com/catalog.jpg"
  }'
```

### Using Python

```python
import requests

url = "http://localhost:8001/api/v1/create-image"
data = {
    "user_id": "user123",
    "api_key": "your_api_key",
    "catalog_id": "catalog456",
    "user_image_url": "https://example.com/user.jpg",
    "catalog_image_url": "https://example.com/catalog.jpg"
}

response = requests.post(url, json=data)
print(response.json())
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_URL` | Django backend URL | `http://localhost:8000` |
| `AI_PROVIDER` | AI provider to use | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | Required for OpenAI |
| `GOOGLE_API_KEY` | Google API key | Required for Gemini |
| `GOOGLE_PROJECT_ID` | Google Cloud project ID | Required for Gemini/Imagen |
| `GOOGLE_LOCATION` | Google Cloud location | `us-central1` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON path | Optional |
| `SERVICE_NAME` | Service name | `sakura-rasa-inference` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `THROTTLE_RPM` | Requests per minute limit | `10` |
| `PORT` | Server port | `8001` |

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `aiohttp`: Async HTTP client
- `openai`: OpenAI API client
- `python-dotenv`: Environment variable management
- `pydantic`: Data validation

## License

MIT
