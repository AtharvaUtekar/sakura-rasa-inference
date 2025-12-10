# Gemini Provider Setup Guide

## Current Status

Your Gemini API key is configured: `AIzaSyBI1hen01ArzGbiPo-YzPECqz4MDUX39ns`

## Important Note

The Gemini API key alone can be used for:
- ✅ Image analysis and understanding
- ✅ Prompt enhancement and generation
- ❌ **Image generation** (requires Imagen API with Google Cloud project)

## For Image Generation

To generate images, you need:

1. **Google Cloud Project ID** - Set `GOOGLE_PROJECT_ID` in `.env`
2. **Imagen API enabled** - Enable Imagen API in your Google Cloud project
3. **Authentication** - Either:
   - Service account JSON file (set `GOOGLE_APPLICATION_CREDENTIALS`)
   - Or OAuth2 credentials

## Quick Setup Steps

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable "Vertex AI API" and "Imagen API"
4. Get your Project ID
5. Add to `.env`:
   ```
   GOOGLE_PROJECT_ID=your-actual-project-id
   ```

## Current Configuration

Your `.env` should have:
```env
AI_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSyBI1hen01ArzGbiPo-YzPECqz4MDUX39ns
GOOGLE_PROJECT_ID=your_google_project_id  # ← Update this
GOOGLE_LOCATION=us-central1
```

## Testing

Once `GOOGLE_PROJECT_ID` is set, test with:
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

## Alternative: Use OpenAI for Image Generation

If you don't have a Google Cloud project, you can use OpenAI DALL-E:
```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
```

