"""Private feedback must persist and remain scoped to its author."""
import importlib.util
import asyncio
from types import SimpleNamespace

import pytest


def module_under_test():
    assert importlib.util.find_spec('app.api.client.v1.feedback'), 'Private feedback API has not been implemented'
    from app.api.client.v1 import feedback
    return feedback


def test_feedback_rejects_blank_and_oversized_content():
    module_under_test()
    from app.schemas.feedback import FeedbackCreate
    from pydantic import ValidationError
    for title, content in [('   ', 'hello'), ('title', '\n '), ('x'*81, 'hello'), ('title', 'x'*2001)]:
        with pytest.raises(ValidationError):
            FeedbackCreate(category='issue', title=title, content=content)
    assert FeedbackCreate(category='issue', title=' Test ', content=' Details ').title == 'Test'


def test_feedback_persists_and_is_private():
    client_api=module_under_test()
    from app.api.backoffice.v1 import feedback as admin_api
    from app.schemas.feedback import FeedbackCreate, FeedbackUpdate
    from app.models.feedback import Feedback
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from fastapi import HTTPException

    async def run():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Feedback.__table__.create)
        factory=async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            owner=SimpleNamespace(id=17)
            other=SimpleNamespace(id=18)
            created=await client_api.create_feedback(FeedbackCreate(category='issue',title='手机输入',content='键盘遮挡'), db=db, current_user=owner)
            item_id=created['data']['id']
        # A new DB session verifies persistence beyond the request.
        async with factory() as db:
            listed=await client_api.list_feedback(offset=0,limit=20,db=db,current_user=owner)
            assert listed['data']['items'][0]['id']==item_id
            assert listed['data']['items'][0]['status']=='pending'
            assert (await client_api.list_feedback(offset=0,limit=20,db=db,current_user=other))['data']['items']==[]
            with pytest.raises(HTTPException) as error:
                await client_api.get_feedback(item_id,db=db,current_user=other)
            assert error.value.status_code==404
            updated=await admin_api.update_feedback(item_id,FeedbackUpdate(status='replied',reply='已记录并修复'),db=db,current_admin=SimpleNamespace(id=3))
            assert updated['data']['status']=='replied'
            own=await client_api.get_feedback(item_id,db=db,current_user=owner)
            assert own['data']['reply']=='已记录并修复'
            assert 'user_id' not in own['data']
        await engine.dispose()
    asyncio.run(run())


def test_reply_requires_text_and_backoffice_permission():
    module_under_test()
    from app.schemas.feedback import FeedbackUpdate
    from app.api.backoffice.v1.feedback import router
    from app.api.backoffice.deps import require_content_manager_admin
    from pydantic import ValidationError
    from fastapi import HTTPException
    with pytest.raises(ValidationError):
        FeedbackUpdate(status='replied',reply='  ')
    for route in router.routes:
        assert require_content_manager_admin in [dep.call for dep in route.dependant.dependencies]
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_content_manager_admin(SimpleNamespace(is_root_admin=False,can_manage_admins=False)))
    assert error.value.status_code==403


def test_feedback_http_auth_validation_and_reply_flow():
    client_api = module_under_test()
    from app.api.backoffice.v1 import feedback as admin_api
    from app.api.client.deps import get_current_user
    from app.api.backoffice.deps import get_current_admin
    from app.db.session import get_db
    from app.models.feedback import Feedback
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    async def run():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Feedback.__table__.create)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(client_api.router, prefix='/feedback')
        app.include_router(admin_api.router, prefix='/admin/feedback')
        async def database():
            async with sessions() as db:
                yield db
        app.dependency_overrides[get_db] = database
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as http:
                assert (await http.get('/feedback')).status_code == 401
                app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
                assert (await http.post('/feedback', json={'category':'issue','title':'  ','content':'test'})).status_code == 422
                response = await http.post('/feedback', json={'category':'issue','title':'手机问题','content':'测试内容','user_id':99})
                assert response.status_code == 200
                feedback_id = response.json()['data']['id']
                assert len((await http.get('/feedback')).json()['data']['items']) == 1
                app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=18)
                assert (await http.get(f'/feedback/{feedback_id}')).status_code == 404
                app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=3,is_root_admin=False,can_manage_admins=False)
                assert (await http.patch(f'/admin/feedback/{feedback_id}',json={'status':'replied','reply':'reply'})).status_code == 403
                app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=3,is_root_admin=False,can_manage_admins=True)
                assert (await http.patch(f'/admin/feedback/{feedback_id}',json={'status':'replied','reply':'已处理'})).status_code == 200
                assert (await http.patch(f'/admin/feedback/{feedback_id}',json={'status':'closed'})).status_code == 200
                app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
                result = (await http.get(f'/feedback/{feedback_id}')).json()['data']
                assert result['status'] == 'closed'
                assert result['reply'] == '已处理'
                assert 'user_id' not in result
                assert (await http.get('/feedback?limit=1000')).status_code == 422
        finally:
            await engine.dispose()
    asyncio.run(run())
