"""Image generation routes — authenticated, persists prompt + result into the conversation."""
from fastapi import APIRouter, Depends

from backend.models import ImageRequest, ImageResponse
from backend.image_service import ImageGenerationService
from backend import database as db
from backend import auth
from backend.exceptions import ChatlyError
from backend.logging_config import logger
from backend.chat_routes import _verify_ownership

router = APIRouter(prefix="/api/images", tags=["images"])
_service = ImageGenerationService()


@router.post("/generate", response_model=ImageResponse)
def generate_image(body: ImageRequest, user: dict = Depends(auth.get_current_user)):
    if body.conversation_id:
        _verify_ownership(body.conversation_id, user["id"])
        conversation = db.get_conversation(body.conversation_id)
    else:
        title = "🖼️ " + (body.prompt[:26] + "..." if len(body.prompt) > 26 else body.prompt)
        conversation = db.create_conversation(user["id"], title)

    db.add_message(conversation["id"], "user", body.prompt, message_type="text")

    try:
        result = _service.generate(body.prompt, body.style, body.width, body.height)
        db.add_message(
            conversation["id"], "assistant", body.prompt, message_type="image",
            extra={"image": result["image"], "provider": result["provider"]},
        )
        return ImageResponse(success=True, image=result["image"], provider=result["provider"], conversation_id=conversation["id"])
    except ChatlyError as exc:
        logger.warning("Image generation error: %s", exc.message)
        return ImageResponse(success=False, error=exc.message, conversation_id=conversation["id"])
