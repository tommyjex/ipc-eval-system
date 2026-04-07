from .health import router
from .datasets import router as datasets_router
from .evaluation_data import router as evaluation_data_router
from .annotations import router as annotations_router

__all__ = ["router", "datasets_router", "evaluation_data_router", "annotations_router"]
