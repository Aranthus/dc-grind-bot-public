class PromptFunctions:
    """Helper functions for text manipulation in prompts"""
    
    # Replacement probability ranges (in percentage)
    TYPING_MISTAKE_CHANCE = (10, 25)  # 10% to 25% chance for typing mistakes
    CASUAL_REPLACEMENT_CHANCE = (15, 30)  # 15% to 30% chance for casual replacements
    
    # Common typing mistakes for more natural responses
    TYPING_MISTAKES = {
        'th': 't',
        'ing': 'in',
        'you': 'u',
        'are': 'r',
        'please': 'pls',
        'thanks': 'thx',
        'right': 'rite',
        'night': 'nite',
        'with': 'wit',
        'what': 'wat',
        'yeah': 'yea'
    }

    # Common casual language replacements
    CASUAL_REPLACEMENTS = {
        'you': 'u',
        'your': 'ur',
        'are': 'r',
        'please': 'pls',
        'thanks': 'thx',
        'right now': 'rn',
        'going to': 'gonna',
        'want to': 'wanna',
        'idk': "i don't know",
        'tbh': 'to be honest',
        'rekt': 'wrecked',
        'af': 'as fuck'
    }

    # Crypto slang replacements
    CRYPTO_SLANG = {
        'scam': 'rug',
        'manipulated': 'rigged',
        'lose money': 'get rekt',
        'trades': 'ape in',
        'sell': 'paper hands',
        'hold': 'diamond hands',
        'all in': 'degen play',
        'research': 'dyor',
        'amazing project': 'gem',
        'scammer': 'rugger',
        'lost everything': 'got rugged',
        'new project': 'fresh mint',
        'good investment': 'based'
    }

    # Chat management prompts
    COMBINE_PROMPT = """Please combine these messages naturally maintaining context and flow
    {messages}
    """

    INIT_CHAT_PROMPT = """You are now in a casual conversation Remember to
     Keep responses natural and conversational
     Use casual language and internet slang when appropriate
     Maintain the flow of conversation
     Stay friendly and engaging
     Always respond in context

    CRITICAL LANGUAGE RULES
    1 You ONLY understand English no other languages
    2 Respond to non English with confusion what ???
    3 Never try to understand or translate other languages
    4 Keep responses casual and use internet slang
    5 Stay in character as an English only speaker
    """

    USER_CONTEXT_PROMPT = '''Previous messages for context
    {context}

    Current user {username}
    Message {message}
    '''

    @classmethod
    def _should_apply_replacement(cls):
        """Determine if a replacement should be applied based on probability"""
        import random
        return random.random() < random.uniform(
            cls.TYPING_MISTAKE_CHANCE[0] / 100,
            cls.TYPING_MISTAKE_CHANCE[1] / 100
        )

    @classmethod
    def _should_apply_casual(cls):
        """Determine if a casual replacement should be applied based on probability"""
        import random
        return random.random() < random.uniform(
            cls.CASUAL_REPLACEMENT_CHANCE[0] / 100,
            cls.CASUAL_REPLACEMENT_CHANCE[1] / 100
        )

    @classmethod
    def apply_replacements(cls, text):
        """Apply replacements with probability checks"""
        if not text:
            return text

        words = text.split()
        result = []
        
        for word in words:
            word_lower = word.lower()
            
            # Check for casual replacements
            if cls._should_apply_casual():
                for original, replacement in cls.CASUAL_REPLACEMENTS.items():
                    if original.lower() in word_lower:
                        word = word.replace(original, replacement)
                        break
            
            # Check for typing mistakes
            if cls._should_apply_replacement():
                for original, replacement in cls.TYPING_MISTAKES.items():
                    if original.lower() in word_lower:
                        word = word.replace(original, replacement)
                        break
            
            result.append(word)
        
        return ' '.join(result)
