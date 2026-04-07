import os

# Set a default value for GEMINI_API_KEY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'default_value')

# Validate GEMINI_API_KEY
if GEMINI_API_KEY == 'default_value':
    raise ValueError("GEMINI_API_KEY is not set. Please set it in your environment variables.")

# Proceed with the rest of the configuration...