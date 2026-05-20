class CarouselAIException(Exception):
    """Base exception class for all CarouselAI errors."""
    pass

class ResourceNotFoundError(CarouselAIException):
    """Raised when a requested resource (brand profile, font, etc.) cannot be found."""
    pass

class PipelineError(CarouselAIException):
    """Raised when a stage in the generation pipeline fails."""
    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage
