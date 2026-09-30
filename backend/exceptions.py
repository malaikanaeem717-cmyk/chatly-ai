"""Custom exceptions so the API can return clean, consistent, safe error messages."""


class ChatlyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthError(ChatlyError):
    def __init__(self, message: str = "Authentication failed."):
        super().__init__(message, status_code=401)


class FileValidationError(ChatlyError):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class DocumentProcessingError(ChatlyError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class EmbeddingError(ChatlyError):
    def __init__(self, message: str = "Embedding generation failed."):
        super().__init__(message, status_code=500)


class LLMProviderError(ChatlyError):
    def __init__(self, message: str = "The AI provider is temporarily unavailable."):
        super().__init__(message, status_code=502)


class ImageGenerationError(ChatlyError):
    def __init__(self, message: str = "Image generation failed."):
        super().__init__(message, status_code=502)


class NotFoundError(ChatlyError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(message, status_code=404)
