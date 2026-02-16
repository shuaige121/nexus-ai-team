"""Organization structure API routes."""

from fastapi import APIRouter
from dashboard.backend.mock_data import MOCK_ORG, get_org_tree

router = APIRouter(prefix="/api/org", tags=["organization"])


@router.get("")
async def get_org():
    """获取完整组织架构。"""
    return MOCK_ORG


@router.get("/tree")
async def get_tree():
    """获取树形结构（前端渲染用）。"""
    return get_org_tree()
