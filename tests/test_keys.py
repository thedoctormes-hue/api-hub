"""Тесты для /keys роутов."""

import pytest
from src.models.user import User
from src.models.provider import Provider
from src.models.api_key import ApiKey


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_create_key_success(client):
    """Успешное создание ключа."""
    ac, session = client

    # Создаём провайдера и пользователя в тестовой БД
    provider = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="default_user",
        email="default@example.com",
        api_key="test-master-key",
    )
    session.add(user)
    await session.commit()

    response = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "sk-test-123", "alias": "тестовый"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "openrouter"
    assert data["alias"] == "тестовый"
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_key_provider_not_found(client):
    """Создание ключа с несуществующим провайдером → 404."""
    ac, _ = client
    response = await ac.post(
        "/keys/",
        params={"provider_name": "nonexistent", "api_key": "sk-test"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_keys_empty(client):
    """Список ключей при пустой базе."""
    ac, _ = client
    response = await ac.get("/keys/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_keys_with_data(client):
    """Список ключей с данными."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider"] == "test_provider"
    assert data[0]["alias"] == "основной"


@pytest.mark.asyncio
async def test_delete_key_not_found(client):
    """Удаление несуществующего ключа → 404."""
    ac, _ = client
    import uuid
    response = await ac.delete(f"/keys/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_key_status_not_found(client):
    """Статус несуществующего ключа → 404."""
    ac, _ = client
    import uuid
    response = await ac.get(f"/keys/{uuid.uuid4()}/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_key_duplicate_alias(client):
    """Создание ключа с дублирующимся alias → обновление существующего."""
    ac, session = client

    provider = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="default_user",
        email="default@example.com",
        api_key="test-master-key",
    )
    session.add(user)
    await session.commit()

    # Первый ключ
    response1 = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "sk-first", "alias": "основной"}
    )
    assert response1.status_code == 201
    first_id = response1.json()["id"]

    # Второй ключ с тем же alias — должен обновить первый
    response2 = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "sk-second", "alias": "основной"}
    )
    assert response2.status_code == 201
    second_id = response2.json()["id"]

    # ID должен совпадать (обновление, а не создание нового)
    assert first_id == second_id


@pytest.mark.asyncio
async def test_create_key_empty_api_key(client):
    """Создание ключа с пустым значением api_key."""
    ac, session = client

    provider = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="default_user",
        email="default@example.com",
        api_key="test-master-key",
    )
    session.add(user)
    await session.commit()

    # Пустой api_key — сервер принимает (валидация на уровне БД/бизнес-логики)
    response = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "", "alias": "пустой"}
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_key_inactive_provider(client):
    """Создание ключа для неактивного провайдера → 404."""
    ac, session = client

    provider = Provider(
        name="inactive_provider",
        type="llm",
        base_url="https://inactive.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=False,
        config=None,
    )
    session.add(provider)
    await session.commit()

    response = await ac.post(
        "/keys/",
        params={"provider_name": "inactive_provider", "api_key": "sk-test"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_key_success(client):
    """Успешное удаление ключа (soft delete)."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.delete(f"/keys/{api_key.id}")
    assert response.status_code == 204

    # Проверяем что ключ не появляется в списке
    list_response = await ac.get("/keys/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 0


@pytest.mark.asyncio
async def test_get_key_status_success(client):
    """Успешное получение статуса ключа."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
        last_status="ok",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get(f"/keys/{api_key.id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(api_key.id)
    assert data["provider"] == "test_provider"
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_keys_excludes_deleted(client):
    """Список ключей не включает удалённые (is_active=False)."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    # Активный ключ
    active_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-active",
        key_alias="активный",
        is_active=True,
    )
    # Удалённый ключ
    deleted_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-deleted",
        key_alias="удалённый",
        is_active=False,
    )
    session.add(active_key)
    session.add(deleted_key)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["alias"] == "активный"


@pytest.mark.asyncio
async def test_list_keys_multiple_providers(client):
    """Список ключей с несколькими провайдерами."""
    ac, session = client

    provider1 = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    provider2 = Provider(
        name="anthropic",
        type="llm",
        base_url="https://api.anthropic.com/v1",
        auth_type="header",
        auth_key_name="x-api-key",
        rate_limit=10,
        timeout_sec=30,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider1)
    session.add(provider2)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.flush()

    api_key1 = ApiKey(
        user_id=user.id,
        provider_id=provider1.id,
        key_ref="sk-test-ref-1",
        key_alias="openrouter-key",
    )
    api_key2 = ApiKey(
        user_id=user.id,
        provider_id=provider2.id,
        key_ref="sk-test-ref-2",
        key_alias="anthropic-key",
    )
    session.add(api_key1)
    session.add(api_key2)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    aliases = {k["alias"] for k in data}
    assert "openrouter-key" in aliases
    assert "anthropic-key" in aliases


@pytest.mark.asyncio
async def test_health_check_keys_with_data(client):
    """Получение статуса конкретного ключа с данными."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
        last_status="ok",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get(f"/keys/{api_key.id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(api_key.id)
    assert data["provider"] == "test_provider"


@pytest.mark.asyncio
async def test_delete_key_idempotent(client):
    """Повторное удаление уже удаленного ключа → 204 (idempotent)."""
    ac, session = client

    provider = Provider(
        name="test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
        is_active=False,
    )
    session.add(api_key)
    await session.commit()

    # Удаление уже неактивного ключа → 204 (idempotent behavior)
    response = await ac.delete(f"/keys/{api_key.id}")
    assert response.status_code == 204

    # Ключ по-прежнему неактивен
    from sqlalchemy import select
    from src.models.api_key import ApiKey as ApiKeyModel
    result = await session.execute(
        select(ApiKeyModel).where(ApiKeyModel.id == api_key.id)
    )
    key = result.scalar_one_or_none()
    assert key is not None
    assert key.is_active is False


@pytest.mark.asyncio
async def test_create_key_too_long_alias(client):
    """Создание ключа с длинным alias (>50 символов)."""
    ac, session = client

    provider = Provider(
        name="openrouter",
        type="llm",
        base_url="https://openrouter.ai/api/v1",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=20,
        timeout_sec=30,
        retry_count=3,
        retry_delay_ms=1000,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key",
    )
    session.add(user)
    await session.commit()

    long_alias = "a" * 60
    response = await ac.post(
        "/keys/",
        params={"provider_name": "openrouter", "api_key": "sk-test", "alias": long_alias}
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_key_returns_created_at(client):
    """Созданный ключ содержит created_at."""
    ac, session = client

    provider = Provider(
        name="test_provider_returns",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.commit()

    response = await ac.post(
        "/keys/",
        params={"provider_name": "test_provider_returns", "api_key": "sk-test", "alias": "test"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "created_at" in data
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_get_key_status_inactive_key(client):
    """Статус неактивного ключа → 404."""
    ac, session = client

    provider = Provider(
        name="test_provider_inactive",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
        is_active=False,
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get(f"/keys/{api_key.id}/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_key_status_inactive_provider(client):
    """Статус ключа неактивного провайдера → 404."""
    ac, session = client

    provider = Provider(
        name="inactive_provider_key",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=False,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="test_user",
        email="test@example.com",
        api_key="test-key-2",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="основной",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get(f"/keys/{api_key.id}/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_keys_no_active_users(client):
    """Список ключей пуст если нет активных пользователей."""
    ac, session = client

    user = User(
        name="inactive_user",
        email="inactive@example.com",
        api_key="test-key",
        is_active=False,
    )
    session.add(user)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_key_updates_existing(client):
    """Создание ключа с существующим alias → обновление key_ref."""
    ac, session = client

    provider = Provider(
        name="update_test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.commit()

    # Первый запрос создаёт ключ
    response1 = await ac.post(
        "/keys/",
        params={"provider_name": "update_test_provider", "api_key": "sk-first", "alias": "test-alias"}
    )
    assert response1.status_code == 201
    first_data = response1.json()

    # Второй запрос с тем же alias обновляет существующий
    response2 = await ac.post(
        "/keys/",
        params={"provider_name": "update_test_provider", "api_key": "sk-updated", "alias": "test-alias"}
    )
    assert response2.status_code == 201
    second_data = response2.json()

    # ID тот же
    assert first_data["id"] == second_data["id"]


@pytest.mark.asyncio
async def test_list_keys_fields_format(client):
    """Список ключей содержит все ожидаемые поля."""
    ac, session = client

    provider = Provider(
        name="format_test_provider",
        type="llm",
        base_url="https://test.example.com",
        auth_type="bearer",
        auth_key_name="Authorization",
        rate_limit=10,
        timeout_sec=15,
        retry_count=2,
        retry_delay_ms=500,
        is_active=True,
        config=None,
    )
    session.add(provider)
    await session.flush()

    user = User(
        name="format_test_user",
        email="format@example.com",
        api_key="format-test-key",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        user_id=user.id,
        provider_id=provider.id,
        key_ref="sk-test-ref",
        key_alias="format-test",
        last_status="ok",
    )
    session.add(api_key)
    await session.commit()

    response = await ac.get("/keys/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    key = data[0]
    assert "id" in key
    assert "user" in key
    assert "provider" in key
    assert "alias" in key
    assert "status" in key
    assert "created_at" in key
