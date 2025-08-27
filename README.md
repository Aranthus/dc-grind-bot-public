# Discord Chat Bot - DC Grind Bot

An advanced Discord bot with AI conversation capabilities, voice channel management, and project information system.

## Features

🤖 **AI-Powered Conversations**
- Multiple AI provider support (OpenAI GPT, Claude, Gemini, Grok, DeepSeek)
- Intelligent conversation management with memory
- Configurable response chances and behavior patterns

🎯 **Smart Interaction**
- Context-aware responses
- Mention detection and reply chains
- Customizable greeting patterns
- Conversation intelligence (experimental)

🎵 **Voice Channel Management**
- Automatic voice channel joining
- Configurable stay duration and intervals
- Random delay mechanisms

🛡️ **Admin Controls**
- Permission-based admin detection
- Silence and control commands
- User exception handling

📊 **Project Information System**
- Supabase integration for project data
- Dynamic project context injection
- Tokenomics and project detail management

🎨 **GIF Integration**
- Tenor API integration for GIF responses
- Context-aware GIF selection

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd dc-grind-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your bot:**
   - Copy `users/config_example.json` to `users/config_your_bot.json`
   - Fill in your API keys and configuration
   - See [Configuration](#configuration) section for details

4. **Run the bot:**
   ```bash
   python discord_selfbot.py
   ```

## Configuration

### Required API Keys

Create a configuration file in `users/` directory based on `config_example.json`:

```json
{
    "discord_token": "YOUR_DISCORD_BOT_TOKEN",
    "api_keys": {
        "gemini": "YOUR_GEMINI_API_KEY",
        "chatgpt": "YOUR_OPENAI_API_KEY",
        "claude": "YOUR_ANTHROPIC_API_KEY",
        "grok": "YOUR_GROK_API_KEY",
        "deepseek": "YOUR_DEEPSEEK_API_KEY",
        "tenor": "YOUR_TENOR_API_KEY"
    },
    "supabase": {
        "url": "YOUR_SUPABASE_PROJECT_URL",
        "anon_key": "YOUR_SUPABASE_ANON_KEY"
    }
}
```

### API Key Setup

**Discord Bot Token:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token

**AI Provider Keys:**
- **OpenAI:** [OpenAI API](https://platform.openai.com/api-keys)
- **Anthropic Claude:** [Anthropic Console](https://console.anthropic.com/)
- **Google Gemini:** [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Grok:** [xAI Console](https://console.x.ai/)
- **DeepSeek:** [DeepSeek Platform](https://platform.deepseek.com/)

**Optional Services:**
- **Tenor GIF API:** [Tenor API](https://tenor.com/gifapi)
- **Supabase:** [Supabase Dashboard](https://supabase.com/dashboard)

### Configuration Options

**Bot Behavior:**
- `online_hour_start/end`: Active hours
- `active_duration`: How long bot stays active
- `afk_duration`: AFK period duration
- `ai_provider`: Choose AI provider (grok, chatgpt, claude, gemini, deepseek)

**Response Settings:**
- `reply_chances`: Probability of responding to different message types
- `message_limit`: Max messages to consider for context
- `temperature`: AI creativity level (0.0-1.0)

**Voice Settings:**
- `enabled`: Enable voice channel features
- `join_interval_hours`: How often to join voice channels
- `stay_duration_minutes`: How long to stay in voice

## File Structure

```
dc-grind-bot/
├── ai_providers/           # AI provider implementations
├── core/                   # Core bot functionality
├── handlers/               # Event handlers
├── models/                 # Data models and configuration
├── prompts/                # AI prompt templates
├── users/                  # User configuration files
├── projects/               # Project information files
├── logs/                   # Log files (git ignored)
└── utils/                  # Helper utilities
```

## Usage

### Basic Commands

The bot responds to:
- Direct mentions (`@botname`)
- Replies to bot messages
- Questions and conversations
- Configured greeting patterns

### Admin Commands

Admins can control the bot with specific commands (configured in settings).

### Project System

The bot can provide information about configured projects when asked. Projects are managed through the Supabase integration.

## Development

### Adding New AI Providers

1. Create a new provider class in `ai_providers/`
2. Inherit from `BaseAIProvider`
3. Implement required methods
4. Register in `ai_providers/__init__.py`

### Custom Prompts

Add custom prompt templates in `prompts/` directory and configure via `prompt_type` setting.

## Security

⚠️ **Important Security Notes:**
- Never commit configuration files with real API keys
- All sensitive files are git-ignored
- Use environment variables in production
- Regularly rotate API keys

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for educational and personal use. Ensure compliance with Discord's Terms of Service and API usage guidelines.

## Support

For issues and questions:
1. Check existing issues in the repository
2. Create a new issue with detailed information
3. Include relevant log files (remove sensitive information)

---

**Note:** This bot is designed for educational purposes. Always follow Discord's Terms of Service and API rate limits.
