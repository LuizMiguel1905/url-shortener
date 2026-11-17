from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from app import cache, redirects, services
from app.database import SessionLocal
from app.schemas import LinkCreate, LinkOut

router = APIRouter()


@router.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
def create_link(payload: LinkCreate) -> LinkOut:
    try:
        with SessionLocal() as db:
            link = services.create_link(db, str(payload.url), payload.custom_code)
            created = LinkOut.from_model(link)
    except services.CodeUnavailableError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Código indisponível") from None
    except services.CodeGenerationError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Não foi possível gerar um código único"
        ) from None
    cache.set_target_url(created.code, created.target_url)
    return created


@router.get("/{code}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
def redirect(code: str) -> RedirectResponse:
    target_url = redirects.lookup_target_url(code)
    if target_url is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link não encontrado")
    return RedirectResponse(target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
