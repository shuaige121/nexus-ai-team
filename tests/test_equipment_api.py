#!/usr/bin/env python3
"""
Test Equipment API endpoints without full gateway initialization
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from fastapi import FastAPI
from equipment.manager import EquipmentManager

# Create a minimal FastAPI app with equipment endpoints
app = FastAPI()
equipment_manager = EquipmentManager()


@app.get("/api/equipment")
async def list_equipment(enabled_only: bool = False):
    """List all registered equipment."""
    if not equipment_manager:
        return {"ok": False, "error": "Equipment manager not initialized"}

    try:
        equipment_list = equipment_manager.list_equipment(enabled_only=enabled_only)
        return {"ok": True, "equipment": equipment_list, "count": len(equipment_list)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/equipment/{name}")
async def get_equipment(name: str):
    """Get equipment details by name."""
    if not equipment_manager:
        return {"ok": False, "error": "Equipment manager not initialized"}

    try:
        equipment = equipment_manager.get_equipment(name)
        if not equipment:
            return {"ok": False, "error": f"Equipment not found: {name}"}
        return {"ok": True, "equipment": equipment}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/equipment/{name}/run")
async def run_equipment(name: str, params: dict | None = None):
    """Execute an equipment script."""
    if not equipment_manager:
        return {"ok": False, "error": "Equipment manager not initialized"}

    try:
        result = equipment_manager.run_equipment(name, params)
        return {"ok": result["status"] == "success", **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_equipment_api():
    """Test equipment API endpoints"""
    print("\n" + "="*60)
    print("测试 2: 设备列表 API")
    print("="*60)

    client = TestClient(app)

    # Test 1: List all equipment
    print("\n1. GET /api/equipment (列出所有设备)")
    response = client.get("/api/equipment")
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ✗ 请求失败")
        return False

    data = response.json()
    print(f"   响应: ok={data.get('ok')}, count={data.get('count')}")

    if not data.get("ok"):
        print(f"   ✗ API 返回错误: {data.get('error')}")
        return False

    print(f"   ✓ 成功获取设备列表")

    equipment_list = data.get("equipment", [])
    print(f"\n   设备列表 ({len(equipment_list)}):")
    for eq in equipment_list:
        print(f"     - {eq['name']}: {eq['description']}")

    # Test 2: Get specific equipment
    print("\n2. GET /api/equipment/health_check (获取特定设备)")
    response = client.get("/api/equipment/health_check")
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ✗ 请求失败")
        return False

    data = response.json()
    if not data.get("ok"):
        print(f"   ✗ API 返回错误: {data.get('error')}")
        return False

    equipment = data.get("equipment")
    print(f"   ✓ 成功获取设备: {equipment['name']}")
    print(f"     描述: {equipment['description']}")
    print(f"     脚本: {equipment['script_path']}")
    print(f"     启用: {equipment['enabled']}")
    print(f"     调度: {equipment['schedule']}")

    # Test 3: Run equipment via API
    print("\n3. POST /api/equipment/health_check/run (执行设备)")
    response = client.post("/api/equipment/health_check/run")
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ✗ 请求失败")
        return False

    data = response.json()
    if not data.get("ok"):
        print(f"   ✗ API 返回错误: {data.get('error')}")
        return False

    print(f"   ✓ 成功执行设备")
    print(f"     状态: {data.get('status')}")

    output = data.get("output", {})
    if output:
        print(f"     健康状态: {output.get('status')}")
        print(f"     摘要: {output.get('summary')}")

    # Test 4: List enabled only
    print("\n4. GET /api/equipment?enabled_only=true (仅列出启用的设备)")
    response = client.get("/api/equipment?enabled_only=true")
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ✗ 请求失败")
        return False

    data = response.json()
    if not data.get("ok"):
        print(f"   ✗ API 返回错误: {data.get('error')}")
        return False

    print(f"   ✓ 成功获取启用的设备列表 (数量: {data.get('count')})")

    # Test 5: Get non-existent equipment (error handling)
    print("\n5. GET /api/equipment/nonexistent (错误处理测试)")
    response = client.get("/api/equipment/nonexistent")
    print(f"   状态码: {response.status_code}")

    if response.status_code != 200:
        print(f"   ✗ 请求失败")
        return False

    data = response.json()
    if data.get("ok"):
        print(f"   ✗ 应该返回错误但返回成功")
        return False

    print(f"   ✓ 正确返回错误: {data.get('error')}")

    return True


if __name__ == "__main__":
    try:
        success = test_equipment_api()
        print("\n" + "="*60)
        if success:
            print("✓ 所有 API 测试通过")
            sys.exit(0)
        else:
            print("✗ API 测试失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if equipment_manager:
            equipment_manager.shutdown()
