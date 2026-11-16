from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app import services
from app.database import DbSession
from app.schemas import LinkCreate, LinkOut

router = APIRouter()


@router.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
def create_link(payload: LinkCreate, db: DbSession) -> LinkOut:
    try:
        link = services.create_link(db, str(payload.url), payload.custom_code)
    except services.CodeUnavailableError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Código indisponível") from None
    except services.CodeGenerationError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Não foi possível gerar um código único"
        ) from None
    return LinkOut.from_model(link)


@router.get("/{code}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def redirect(code: str, db: DbSession) -> RedirectResponse:
    target_url = services.resolve_link(db, code)
    if target_url is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link não encontrado")
    return RedirectResponse(target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
